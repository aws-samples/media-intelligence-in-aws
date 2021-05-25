from os import environ
from json import dumps,loads
from boto3 import client,resource
from botocore import config
from boto3.dynamodb.conditions import Key
from concurrent.futures import ThreadPoolExecutor, as_completed


client_config = config.Config(
    max_pool_connections=25
)
REGION = environ['AWS_REGION']
REKOGNITION = client('rekognition',config=client_config)
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
S3 =client('s3')
LAMBDA = client('lambda')
LABELS_DETECTED = []
FAILED_FRAMES = []
NO_LABELS = []
def lambda_handler(event, context):

    response = {
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {}
    }

    print("Processing the event: \n ", dumps(event))

    if 'Records' in event:
        message = loads(
            event['Records'][0]['Sns']['Message']
        )
    else:
        print("No valid event, abortin execution")
        exit(0)

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
    job_status = start_rekognition_label_job(dynamo_record,frame_output_path,)
    response['body']['data'] = job_status

    objects,scenes,sentiments = split_objects_scenes(LABELS_DETECTED)

    index_objects = invoke_elasticsearch_index_lambda(objects,'objects',message)
    index_scenes = invoke_elasticsearch_index_lambda(scenes,'scenes',message)
    index_sentiments = invoke_elasticsearch_index_lambda(sentiments,'sentiments',message)

    print("Completed labels: "+str(len(LABELS_DETECTED)))
    print("No labels: "+str(len(NO_LABELS)))
    print("Failed frames : "+str(len(FAILED_FRAMES)))


    return response

def start_rekognition_label_job(dynamo_record,output_path,start_from="",lambda_arn=""):
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

    response['es_results'] = []
    print("Frames to analyze: "+str(len(object_name_list)))
    with TABLE.batch_writer() as batch:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(
                    get_object_scene_labels,frame,dynamo_record,batch,
                ) for frame in object_name_list
            ]
            for r in as_completed(futures):
                if r.result() is not False:
                    LABELS_DETECTED.append(r.result())

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

def get_object_scene_labels(frame,dynamo_record,batch,min_confidence=70,name_identifier="_frame_"):
    if REKOGNITION is False:
        raise Exception("Rekognition client creation failed")
    objects_scene_in_frame = []
    timestamp_fraction_ms = 1000 / dynamo_record['SampleRate']
    frame_name = (frame.split('/')[-1]).replace('.jpg','')
    frame_number = int(frame_name.split('.')[-1])
    try:
        job_response = REKOGNITION.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': environ['DEST_S3_BUCKET'],
                    'Name': frame
                }
            },
            MaxLabels=10,
            MinConfidence=min_confidence
        )
    except Exception as e:
        print("Rekognition label detection exception on file: " + frame + " \n", e)
        FAILED_FRAMES.append({'frame_name': frame, 'reason': e})
        return False
    else:
        timestamp = int(frame_number * timestamp_fraction_ms)
        if len(job_response['Labels']) > 0:
            individual_results = {
                'S3Key': dynamo_record['S3Key'],
                'AttrType': 'ana/osc/' + str(dynamo_record['SampleRate']) + '/{Timestamp}'.format(Timestamp=timestamp),
                'JobId': dynamo_record['JobId'],
                'DetectedLabels': dumps(job_response['Labels']),
                'FrameS3Key': frame
            }
            batch.put_item(Item=individual_results)
            unique_labels = unique_labels_in_image(job_response['Labels'])
            for label, data in unique_labels.items():
                objects_scene_in_frame.append({
                    'object_scene': label,
                    'accuracy': data['avg_confidence']
                })
            return {
                timestamp: objects_scene_in_frame
            }
        else:
            NO_LABELS.append(frame)
            return False

def split_objects_scenes(labels):
    object_labels = {}
    scene_labels = {}
    sentiment_labels = {}
    try:
        scene_dictionary_obj = S3.get_object(
            Bucket=environ['DEST_S3_BUCKET'],
            Key=environ['OSC_DICT']
        )
    except Exception as e:
        print("Failed retreiving dictionary \n",e)
        return False,False,False
    else:
        scene_dictionary = loads(scene_dictionary_obj['Body'].read().decode('UTF-8'))

    print(scene_dictionary)

    for item in labels:
        item_scene_labels = []
        item_obj_labels = []
        item_sent_labels = []
        frame = ""
        for id,data in item.items():
            frame = id
            for label in data:
                if label['object_scene'] in scene_dictionary['scenes']:
                    item_scene_labels.append({
                        'scene':label['object_scene'],
                        'accuracy':label['accuracy']
                    })
                elif label['object_scene'] in scene_dictionary['sentiments']:
                    item_sent_labels.append({
                        'sentiment':label['object_scene'],
                        'accuracy':label['accuracy']
                    })
                else:
                    item_obj_labels.append({
                        'object':label['object_scene'],
                        'accuracy':label['accuracy']
                    })
        if item_obj_labels != []:
            object_labels[frame] = item_obj_labels
        if item_scene_labels != []:
            scene_labels[frame] = item_scene_labels
        if item_sent_labels != []:
            sentiment_labels[frame] = item_sent_labels

    return object_labels,scene_labels,sentiment_labels

def invoke_elasticsearch_index_lambda(es_results,type,message):
    try:
        ans = LAMBDA.invoke(
            FunctionName=environ['ES_LAMBDA_ARN'],
            InvocationType='RequestResponse',
            Payload=dumps({
                'results': es_results,
                'type': type,
                'S3_Key': message['S3Key'],
                'SampleRate': message['SampleRate'],
                'JobId': message['JobId']
            })
        )
    except Exception as e:
        print("Exception while invoking ElasticSearch Indexing lambda \n",e)
        return False
    else:
        print(ans)
        return True
