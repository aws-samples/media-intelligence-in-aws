from os import environ
from json import dumps,loads
from boto3 import client,resource
from boto3.dynamodb.conditions import Key


REGION = environ['AWS_REGION']
REKOGNITION = client('rekognition')
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
S3 =client('s3')
LAMBDA = client('lambda')

def lambda_handler(event, context):

    response = {
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {}
    }

    print("Processing the event: \n ", dumps(event))
    # S3Key,JobId,OutputPath
    message = loads(
        event['Records'][0]['Sns']['Message']
    )
    print('Starting object/scene classification ...')
    s3_key = message['S3Key'].replace('s3://{}/'.format(environ['IN_S3_BUCKET']), '')
    JobId = message['JobId']
    dynamo_record = TABLE.query(
        IndexName='JobIdIndex',
        KeyConditionExpression=
        Key('S3Key').eq(s3_key) & Key('JobId').eq(JobId)
    )['Items'][0]

    if dynamo_record is False or dynamo_record == []:
        raise Exception("No item found on DynamoDB with: " + s3_key + " & " + JobId)

    frame_output_path = message['OutputPath']
    dynamo_record['SampleRate'] = message['SampleRate']
    job_status = start_rekognition_label_job(dynamo_record,frame_output_path)
    response['body']['data'] = job_status

    ans = LAMBDA.invoke(
        FunctionName=environ['ES_LAMBDA_ARN'],
        InvocationType='RequestResponse',
        Payload=dumps({
            'results': response['es_results'],
            'type': 'object_scene_classification',
            'S3_Key': message['S3Key']
        })
    )

    print(ans)

    return response

def start_rekognition_label_job(dynamo_record,output_path,min_confidence=70,name_identifier="_frame_"):
    response = {}
    if S3 is False:
        raise Exception("S3 client creation failed")

    s3_bucket = environ['DEST_S3_BUCKET']
    s3_objects = get_s3_object_list(s3_bucket,output_path.replace("s3://"+s3_bucket+"/",""))

    if s3_objects is False:
        print("Empty folder "+output_path+" task aborted")
        return {"msg":"Empty folder "+output_path+" task aborted"}

    object_name_list = process_s3_object_list(s3_objects)
    if len(object_name_list) <= 0:
        print("No frames found on " + output_path + ", verify your MediaConvert job, only jpg and png files supported")
        return {"msg": "No frames found verify your MediaConvert job, only jpg and png files supported"}

    if REKOGNITION is False:
        raise Exception("Rekognition client creation failed")

    failed_frames = []
    current_frame = 0
    timestamp_fraction_ms = 1000/dynamo_record['SampleRate']
    response['es_results'] = []
    with TABLE.batch_writer() as batch:
        for file_name in object_name_list:
            objects_scene_in_frame = []
            try:
                job_response = REKOGNITION.detect_labels(
                    Image={
                        'S3Object': {
                            'Bucket': s3_bucket,
                            'Name': file_name
                        }
                    },
                    MaxLabels=10,
                    MinConfidence=min_confidence
                )
            except Exception as e:
                print("Rekognition job creation exception on file: "+file_name+" \n", e)
                failed_frames.append({'frame_name':file_name,'reason':e})
            else:
                timestamp = int(current_frame*timestamp_fraction_ms)
                individual_results={
                    'S3Key':dynamo_record['S3Key'],
                    'AttrType':'ana/osc/'+str(dynamo_record['SampleRate'])+'/{Timestamp}'.format(Timestamp=timestamp),
                    'JobId':dynamo_record['JobId'],
                    'ObjectSceneDetectedLabels':dumps(job_response['Labels']),
                    'FrameS3Key':file_name
                }
                batch.put_item(Item=individual_results)
                unique_labels = unique_labels_in_image(job_response['Labels'])
                print(unique_labels)
                for label,data in unique_labels.items():
                    objects_scene_in_frame.append({
                        'object_scene': label,
                        'accuracy': data['avg_confidence']
                    })
                response['es_results'].append({
                    timestamp: objects_scene_in_frame
                })
            current_frame += 1

    response['msg'] = "Job completed for "+str(len(object_name_list))+" frames"
    response["frames_failed"] = failed_frames

    return response

def get_s3_object_list(s3_bucket,path,marker='',s3_objects=[]):
    try:
        if marker == '':
            s3_response = S3.list_objects(
                Bucket=s3_bucket,
                Delimiter='/',
                EncodingType='url',
                MaxKeys=1000,
                Prefix=path
            )
        else:
            print("Continue from "+marker)
            s3_response = S3.list_objects(
                Bucket=s3_bucket,
                Marker=marker,
                Delimiter='/',
                EncodingType='url',
                MaxKeys=1000,
                Prefix=path
            )
    except Exception as e:
        print("An error occured while listing objects from bucket: "+s3_bucket+" \n",e)
        return False
    else:
        if s3_response['IsTruncated']:
           return s3_response['Contents'] + get_s3_object_list(s3_bucket,path,s3_response['NextMarker'],s3_objects)
        else:
            if 'Contents' not in s3_response:
                return []
            else:
                s3_objects = s3_objects + s3_response['Contents']

    return s3_objects

def process_s3_object_list(s3_objects_list,name_identifier="_frame_"):
    object_name_list = []
    for s3_object in s3_objects_list:
        if (".jpg" in s3_object['Key'] or ".png" in s3_object['Key']) and name_identifier in s3_object['Key']:
            object_name_list.append(s3_object['Key'])

    return object_name_list

def sanitize_string(string_variable):
    string_variable=string_variable.replace("\n","")
    string_variable = string_variable.replace("\"","")
    string_variable = string_variable.replace("/","")
    string_variable = string_variable.replace("\'","")
    string_variable = string_variable.replace("\r","")
    string_variable = string_variable.replace(":","")
    return string_variable


def get_average(self, accumulated, new, n):
    if n == 0 or n == 1:
        return new
    return (accumulated * n + new) / (n + 1)

def unique_labels_in_image(objects,threshold=80):
    unique_objects = {}
    for label in objects:
        if label['Confidence'] < threshold:
            continue
        object_scene = label['Name']
        if object_scene not in unique_objects:
            unique_objects[object_scene] = {
                'total_matches':0,
                'avg_confidence': label['Confidence']
            }
        else:
            unique_objects[object_scene]['total_matches'] += 1
            unique_objects[object_scene]['avg_confidence'] = get_average(unique_objects[object_scene]['avg_confidence'],label['Confidence'],unique_objects[object_scene]['total_matches'])

    return unique_objects