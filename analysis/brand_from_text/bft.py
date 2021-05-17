from os import environ
from boto3 import client, resource
from json import load, dumps, loads
from fuzzyset import FuzzySet
from os import environ
from time import sleep

REKOGNITION = client('rekognition')
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])

def lambda_handler(event, context):
    with open('brands.json') as brands_file:
        brand_set = FuzzySet(load(brands_file))
    
    message = loads(
        event['Records'][0]['Sns']['Message']
    )
    print('Starting text extraction ..')
    detection = REKOGNITION.start_text_detection(
        Video={
            'S3Object': {
                'Bucket': environ['IN_S3_BUCKET'],
                'Name': message['S3Key'] 
            }
        }
    )

    print('Waiting for text extraction job ..')
    response = REKOGNITION.get_text_detection(
        JobId=detection['JobId']
    )
    while(response['JobStatus'] == 'IN_PROGRESS'):
        sleep(1)
        response = REKOGNITION.get_text_detection(
        JobId=detection['JobId']
    )
    
    print('Matching brands ..')
    frames = []
    if len(response['TextDetections']) > 0:
        curr_timestamp = response['TextDetections'][0]['Timestamp']
    else:
        return 0

    # Group text detections by timestamp
    with TABLE.batch_writer() as batch:
        for detection in response['TextDetections']:
            matching_brands = brand_set.get(detection['TextDetection']['DetectedText']) # Gets closest relative brands
            brands = brand_set.get(detection['TextDetection']['DetectedText'])
            if brands:
                matching_brands = list(
                    filter(
                        lambda match: match[0] >= float(environ['SIM_THRESHOLD']),
                        brands
                    )
                )
            else:
                continue
                
            if detection['Timestamp'] != curr_timestamp:
                batch.put_item(Item={
                    'S3Key': message['S3Key'],
                    'AttrType': 'ana/bft/'+str(message['SampleRate'])+'/{Timestamp}'.format(Timestamp=curr_timestamp),
                    'JobId': message['JobId'],
                    'DetectedLabels': dumps(frames)
                })
                print ({
                    'S3Key': message['S3Key'],
                    'AttrType': 'ana/bft/'+str(message['SampleRate'])+'/{Timestamp}'.format(Timestamp=curr_timestamp),
                    'JobId': message['JobId'],
                    'DetectedLabels': dumps(frames)
                })
                frames = []
                curr_timestamp = detection['Timestamp']
            
            frames.append({
                'DetectedText': detection['TextDetection']['DetectedText'],
                'Confidence': detection['TextDetection']['Confidence'],
                'MatchingBrands': matching_brands
            })

        batch.put_item(Item={
            'S3Key': message['S3Key'],
            'AttrType': 'ana/bft/'+str(message['SampleRate'])+'/{Timestamp}'.format(Timestamp=curr_timestamp),
            'JobId': message['JobId'],
            'DetectedLabels': dumps(frames)
        })
        print ({
            'S3Key': message['S3Key'],
            'AttrType': 'ana/bft/'+str(message['SampleRate'])+'/{Timestamp}'.format(Timestamp=curr_timestamp),
            'JobId': message['JobId'],
            'DetectedLabels': dumps(frames)
        })