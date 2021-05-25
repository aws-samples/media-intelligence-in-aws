from os import environ
from json import dumps,loads
from boto3 import client,resource
from boto3.dynamodb.conditions import Key
from botocore import config
from FaceRekognition import FaceRekognition
from concurrent.futures import ThreadPoolExecutor, as_completed
import cv2
import numpy as np

client_config = config.Config(
    max_pool_connections=25
)

REGION = environ['AWS_REGION']
FACE_REKOGNITION = FaceRekognition(REGION,config=client_config)
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
S3 = client('s3')
S3_BUCKET = resource('s3').Bucket(environ['DEST_S3_BUCKET'])
COLLECTION_ID = environ['CELEBRITY_COLLECTION_ID']
LAMBDA = client('lambda')
EMOTION_RATE = 15
CELEBRITIES_DETECTED = []
SENTIMENTS_DETECTED = []

def lambda_handler(event, context):

    response = {
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {}
    }

    print("Processing the event: \n ", dumps(event))

    message = loads(
        event['Records'][0]['Sns']['Message']
    )
    print('Starting celebrities detection ...')
    s3_key = message['S3Key'].replace('s3://{}/'.format(environ['IN_S3_BUCKET']), '')
    sample_rate = message['SampleRate']
    JobId = message['JobId']
    dynamo_record = TABLE.query(
        KeyConditionExpression=
        Key('S3Key').eq(s3_key) & Key('AttrType').eq('frm/'+str(sample_rate))
    )['Items'][0]

    if dynamo_record is False or dynamo_record == []:
        raise Exception("No item found on DynamoDB with: " + s3_key + " & " + JobId)

    print(dynamo_record)

    frame_output_path = message['OutputPath']
    analysis_list = dynamo_record['analysis']
    analysis_base_name = 'ana/osc/'+str(sample_rate)+'/'
    if "all" not in analysis_list and "osc" not in analysis_list:
        print("Do face detection on frames")
        frames = get_frames_list_s3(S3_BUCKET,frame_output_path)
    else:
        osc_results = TABLE.query(
            KeyConditionExpression=
            Key('S3Key').eq(s3_key) & Key('AttrType').begins_with(analysis_base_name)
        )['Items']
        if osc_results == [] or osc_results is False:
            print("No results saved on dynamo, proceeding face rekognition with all frames")
            frames = get_frames_list_s3(environ['DEST_S3_BUCKET'], frame_output_path)
        else:
            frames = get_frames_list_osc(osc_results)

    celebrity_rekognition = detect_celebrities_from_frames(frames,dynamo_record)

    response['body']['data'] = celebrity_rekognition

    if celebrity_rekognition is False:
        print("Celebirty rekognition FAILED")
        return response

    print(CELEBRITIES_DETECTED)
    print(SENTIMENTS_DETECTED)
    index_celebrities = invoke_elasticsearch_index_lambda(CELEBRITIES_DETECTED,'celebrities',message)
    index_sentiments = invoke_elasticsearch_index_lambda(SENTIMENTS_DETECTED,'sentiments',message)

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

def detect_celebrities_from_frames(frames,dynamo_record,identifier='_frame_',format='.jpg',threshold=80):

    with TABLE.batch_writer() as batch:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(
                    get_celebrities_from_frame, frame, dynamo_record, batch, identifier,threshold,format
                ) for frame in frames
            ]
            for r in as_completed(futures):
                timestamp,celebrities,sentiments = r.result()
                if celebrities is not False:
                    CELEBRITIES_DETECTED[timestamp] = celebrities
                if sentiments is not False:
                    SENTIMENTS_DETECTED[timestamp] = sentiments

    return True

def get_frames_list_s3(s3_bucket,output_path):
    s3_objects = get_s3_object_list(s3_bucket, output_path.replace("s3://" + s3_bucket + "/", ""))

    if s3_objects is False:
        print("Empty folder " + output_path + " task aborted")
        return {"msg": "Empty folder " + output_path + " task aborted"}

    object_name_list = process_s3_object_list(s3_objects)
    if len(object_name_list) <= 0:
        print("No frames found on " + output_path + ", verify your MediaConvert job, only jpg and png files supported")
        return {"msg": "No frames found verify your MediaConvert job, only jpg and png files supported"}

    return object_name_list

def get_frames_list_osc(osc_results):
    frame_list = []
    for object_result in osc_results:
        if 'ObjectSceneDetectedLabels' not in object_result:
            continue
        #print(object_result['ObjectSceneDetectedLabels'])
        object_scene_labels = loads(object_result['ObjectSceneDetectedLabels'])
        for object_scene_label in object_scene_labels:
            if object_scene_label['Name'] == 'Face' or object_scene_label['Name'] == 'Person':
                frame_list.append(object_result['FrameS3Key'])
                break
    return frame_list

def get_analysis_dynamo_results(s3_key,analysis_base_name):
    osc_results = TABLE.query(
        KeyConditionExpression=
        Key('S3Key').eq(s3_key) & Key('AttrType').begins_with(analysis_base_name + "0")
    )['Items']
    all_results = []
    i = 0
    while i < 10:
        for result in osc_results:
            frame_number = result["AttrType"].split('/')[-1]
            frame_name = (result['FrameS3Key'].split('/')[-1]).replace('.jpg', '')
            frame_nn = int(frame_name.split('.')[-1])
            print(frame_nn)
            if result not in all_results:
                all_results.append(result)

        if i < 9:
            osc_results = TABLE.query(
                KeyConditionExpression=
                Key('S3Key').eq(s3_key) & Key('AttrType').between(analysis_base_name + str(i),
                                                                  analysis_base_name + str(i + 1))
            )['Items']
        else:
            osc_results = TABLE.query(
                KeyConditionExpression=
                Key('S3Key').eq(s3_key) & Key('AttrType').begins_with(analysis_base_name + str(i))
            )['Items']
        i += 1
    return all_results

def get_celebrities_from_frame(frame,dynamo_record,batch,identifier = '_frame_',threshold = 80,format='.jpg'):

    s3_key = dynamo_record['S3Key']
    timestamp_fraction_ms = 1000 / dynamo_record['SampleRate']

    frame_name = sanitize_string(frame.split('/')[-1])
    frame_name = frame_name.replace(s3_key, '')
    frame_name = frame_name.replace(s3_key.split('/')[-1], '')
    frame_name = frame_name.replace('.jpg', '')
    frame_name = frame_name.replace(identifier, '')
    frame_number = int(frame_name.split('.')[-1])

    frame_timestamp = int(frame_number * timestamp_fraction_ms)
    dynamo_base_name = "ana/cff/" + str(dynamo_record['SampleRate']) + '/{Timestamp}'.format(Timestamp=frame_timestamp)

    faces = FACE_REKOGNITION.detect_faces_in_image(environ['DEST_S3_BUCKET'], frame)
    if faces is False or faces == []:
        print("No faces found on frame " + frame)
        return frame_timestamp,False,False

    image_raw = S3_BUCKET.Object(frame).get().get('Body').read()
    image = cv2.cvtColor(cv2.imdecode(np.asarray(bytearray(image_raw), dtype="uint8"), cv2.IMREAD_UNCHANGED),
                         cv2.COLOR_BGR2RGB)
    if image is None:
        print("Unable to load image on CV2, further analysis cannot be completed for the frame")
        return frame_timestamp,False,False
    frame_celebrities = {}
    for face in faces:
        bounding_box = face['BoundingBox']
        face_origin, face_dimensions = FACE_REKOGNITION.get_face_box(image.shape, bounding_box)

        cropped_face = FACE_REKOGNITION.crop_face(image, face_origin, face_dimensions, 40)

        encoded_success, buffer = cv2.imencode(format, cropped_face)
        if encoded_success is False:
            print("Error trying to encode image to " + format)
            continue

        face_to_bytes = bytearray(buffer.tobytes())

        celebs_found = FACE_REKOGNITION.detect_faces_from_collection(collection_id=COLLECTION_ID,
                                                                     blob=face_to_bytes)
        if celebs_found is False:
            continue
        if celebs_found['FaceMatches'] != []:
            celebrities = FACE_REKOGNITION.celeb_names_in_image(celebs_found['FaceMatches'], threshold,
                                                                environ['STAGE'])
            for celebrity, data in celebrities.items():
                if celebrity in frame_celebrities:
                    frame_celebrities[celebrity]['total_matches'] += data['total_matches']
                    frame_celebrities[celebrity]['avg_similarity'] = (frame_celebrities[celebrity]['avg_similarity'] +
                                                                      data['avg_similarity']) / \
                                                                     frame_celebrities[celebrity]['total_matches'],
                    frame_celebrities[celebrity]['avg_confidence'] = (frame_celebrities[celebrity]['avg_confidence'] +
                                                                      data['avg_confidence']) / \
                                                                     frame_celebrities[celebrity]['total_matches'],
                else:
                    frame_celebrities[celebrity] = data
                    frame_celebrities[celebrity]['bounding_box'] = bounding_box
                    frame_celebrities[celebrity]['face_emotions'] = get_top_emotions(face['Emotions'],EMOTION_RATE)

    if frame_celebrities != {}:
        individual_results = {
            'S3Key': dynamo_record['S3Key'],
            'AttrType': dynamo_base_name,
            'JobId': dynamo_record['JobId'],
            'CelebritiesDetected': dumps(frame_celebrities),
            'FrameS3Key': frame
        }
        batch.put_item(Item=individual_results)
        return frame_timestamp,prepare_elasticsearch_results(frame_celebrities)
    return frame_timestamp,False,False

def prepare_elasticsearch_results(results):
    frame_face_results = []
    frame_sentiments_results = []
    if results is False or results == []:
        return False,False
    for frame_celebrity, data in results.items():
        frame_face_results.append({
            'celebrity': frame_celebrity,
            'accuracy': data['avg_confidence']
        })
        for emotion in data['face_emotions']:
            frame_sentiments_results.append({
                'sentiment': emotion['Type'],
                'accuracy': emotion['Confidence']
            })
    return frame_face_results,frame_sentiments_results

def get_top_emotions(emotions,threshold = 15):
    top_emotions = []
    for emotion in emotions:
        if emotion['Confidence'] >= threshold:
            top_emotions.append(emotion)
    return top_emotions

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