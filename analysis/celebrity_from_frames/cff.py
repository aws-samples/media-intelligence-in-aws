from os import environ
from json import dumps,loads
from boto3 import client,resource
from boto3.dynamodb.conditions import Key
from FaceRekognition import FaceRekognition
import cv2
import numpy as np


REGION = environ['AWS_REGION']
FACE_REKOGNITION = FaceRekognition(REGION)
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
S3 =client('s3')
S3_BUCKET = S3.Bucket(environ['DEST_S3_BUCKET'])

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
    sample_rate = message['SampleRate']
    JobId = message['JobId']
    dynamo_record = TABLE.query(
        IndexName='JobIdIndex',
        KeyConditionExpression=
        Key('S3Key').eq(s3_key) & Key('JobId').eq(JobId)
    )['Items'][0]

    if dynamo_record is False or dynamo_record == []:
        raise Exception("No item found on DynamoDB with: " + s3_key + " & " + JobId)

    print(dynamo_record)

    analysis_list = dynamo_record['analysis']
    analysis_base_name = 'ana/osc/'+str(sample_rate)
    if "all" not in analysis_list and "osc" not in analysis_list:
        print("Do face detection on frames")
    else:
        osc_results = TABLE.query(
            KeyConditionExpression=
            Key('S3_KEY').eq(s3_key) & Key('ATTR_TYPE').begins_with(analysis_base_name + '/')
        )
        if osc_results == [] or osc_results is False:
            print("No results saved on dynamo, proceeding face rekognition")
            return response
        job = detect_celebrities_from_osc_frames(osc_results)
        print("Use frames results from dynamo")

    frame_output_path = message['OutputPath']
    dynamo_record['SampleRate'] = message['SampleRate']
    job_status = "start_rekognition_label_job(dynamo_record,frame_output_path)"
    response['body']['data'] = job_status
    # TODO
    #   Handle DLQ

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

def detect_celebrities_from_frames(s3_bucket,output_path):
    s3_objects = get_s3_object_list(s3_bucket, output_path.replace("s3://" + s3_bucket + "/", ""))

    if s3_objects is False:
        print("Empty folder " + output_path + " task aborted")
        return {"msg": "Empty folder " + output_path + " task aborted"}

    object_name_list = process_s3_object_list(s3_objects)
    if len(object_name_list) <= 0:
        print("No frames found on " + output_path + ", verify your MediaConvert job, only jpg and png files supported")
        return {"msg": "No frames found verify your MediaConvert job, only jpg and png files supported"}

    for frame in object_name_list:
        faces = FACE_REKOGNITION.find_faces_in_image(s3_bucket, frame)
        if faces is False or faces == []:
            print("No faces found on frame "+frame)
            continue

        image_raw = S3_BUCKET.Object(frame).get().get('Body').read()
        image = cv2.imdecode(np.asarray(bytearray(image_raw), dtype="uint8"), cv2.IMREAD_COLOR)
        if image is None:
            continue
        image_properties = image.shape
        for face in faces:
            bounding_box = face['BoundingBox']
            face_origin, face_dimensions = FACE_REKOGNITION.get_face_box(image.shape, bounding_box)
            #cropped_face =
    return False


