from os import environ
from boto3 import client, resource
from json import load, dumps, loads
from boto3.dynamodb.conditions import Key
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore import config
from unidecode import unidecode
from collections import deque

client_config = config.Config(
    max_pool_connections=25
)

REKOGNITION = client('rekognition', config=client_config)
SNS = client('sns')
S3 = client('s3')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
BRANDS = {}
LAMBDA = client('lambda')

def get_s3_object_list(s3_bucket, path, marker='', s3_objects=[]):
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
        print(f'An error occured while listing objects from bucket: {s3_bucket} \n',e)
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

def sanitize_string(string_variable):
    string_variable=string_variable.replace("\n","")
    string_variable = string_variable.replace("\"","")
    string_variable = string_variable.replace("/","")
    string_variable = string_variable.replace("\'","")
    string_variable = string_variable.replace("\r","")
    string_variable = string_variable.replace(":","")
    return string_variable

def process_s3_object_list(s3_objects_list,name_identifier="_frame_"):
    object_name_list = []
    for s3_object in s3_objects_list:
        if (".jpg" in s3_object['Key'] or ".png" in s3_object['Key']) and name_identifier in s3_object['Key']:
            object_name_list.append(s3_object['Key'])

    return object_name_list

def get_frames_list_s3(s3_bucket, output_path):
    s3_objects = get_s3_object_list(s3_bucket, output_path.replace(f's3://{s3_bucket}/', ""))

    if s3_objects is False:
        print("Empty folder " + output_path + " task aborted")
        return {"msg": "Empty folder " + output_path + " task aborted"}

    object_name_list = process_s3_object_list(s3_objects)
    if len(object_name_list) <= 0:
        print("No frames found on " + output_path + ", verify your MediaConvert job, only jpg and png files supported")
        return {"msg": "No frames found verify your MediaConvert job, only jpg and png files supported"}

    return object_name_list

def get_brands_from_frame(frame, batch, dynamo_record):
    def clean_names(brand):
        brand.update({'Name':unidecode(brand['Name'])})

    frame_timestamp = int(frame.split('.')[-2]) * 1000 / dynamo_record['SampleRate']
    dynamo_base_name = "ana/bfl/" + str(dynamo_record['SampleRate']) + '/{Timestamp}'.format(Timestamp=frame_timestamp)
    brands = REKOGNITION.detect_custom_labels(
            ProjectVersionArn=environ['MODEL_ARN'],
            Image={'S3Object': {
                'Bucket': environ['DEST_S3_BUCKET'],
                'Name': frame
            }},
            MaxResults=3,
            MinConfidence=float(environ['CONFIDENCE_THRESHOLD'])
        )['CustomLabels']

    if len(brands) > 0:
        deque(map(clean_names, brands))
        individual_results = {
            'S3Key': dynamo_record['S3Key'],
            'AttrType': dynamo_base_name,
            'JobId': dynamo_record['JobId'],
            'DetectedLabels': dumps(brands),
            'FrameS3Key': frame
        }
        print(individual_results)
        print(batch.put_item(Item={
            'S3Key': dynamo_record['S3Key'],
            'AttrType': dynamo_base_name,
            'JobId': dynamo_record['JobId'],
            'DetectedLabels': dumps(brands),
            'FrameS3Key': frame
        }))
    return frame_timestamp, brands

def detect_brands_from_frames(frames, dynamo_record):
    # s3_key = dynamo_record['S3Key']
    detected = False
    with TABLE.batch_writer() as batch:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [
                pool.submit(
                    get_brands_from_frame, frame, batch, dynamo_record
                ) for frame in frames
            ]
            for r in as_completed(futures):
                timestamp, brands = r.result()
                if brands:
                    key = str(timestamp)
                    BRANDS[key] = [{
                        'brand': unidecode(brand['Name']),
                        'accuracy': brand['Confidence']
                    } for brand in brands]
                    detected = True
    return detected
                    
                        
def lambda_handler(event, context):
    s3_bucket = environ['DEST_S3_BUCKET']
    print('Starting brand from logo extraction ..')
    message = loads(
        event['Records'][0]['Sns']['Message']
    )  

    frame_output_path = message['OutputPath']
    frame_output_path.replace(f's3://{s3_bucket}/', "")

    dynamo_record = TABLE.query(
        KeyConditionExpression=(Key('S3Key').eq(message['S3Key'])
        & Key('AttrType').eq('frm/{}'.format(message['SampleRate'])))
    )['Items'][0]

    if dynamo_record is False or dynamo_record == []:
        raise Exception("No item found on DynamoDB")
    print(type(message['S3Key']))
    if detect_brands_from_frames( get_frames_list_s3(s3_bucket, frame_output_path), dynamo_record):
        ans = LAMBDA.invoke(
            FunctionName=environ['ES_LAMBDA_ARN'],
            InvocationType='RequestResponse',
            Payload=dumps({
                'results': BRANDS,
                'type': 'brands',
                'S3_Key': message['S3Key'],
                'SampleRate': message['SampleRate'],
                'JobId': message['JobId']
            })
        )
        print(ans)
    