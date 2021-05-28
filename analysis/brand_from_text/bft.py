from os import environ
from boto3 import client, resource
from json import load, dumps, loads
from fuzzyset import FuzzySet
from os import environ
from time import sleep

REKOGNITION = client('rekognition')
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
LAMBDA = client('lambda')

def lambda_handler(event, context):
    es_results = {}
    with open('brands.json') as brands_file:
        brand_set = FuzzySet(load(brands_file))
    
    message = loads(event['Records'][0]['Sns']['Message'])
    
    print('Starting text extraction ..')
    detection = REKOGNITION.start_text_detection(
        Video={
            'S3Object': {
                'Bucket': environ['IN_S3_BUCKET'],
                'Name': message['S3Key'] 
            }
        }
    )

    print('Waiting for text extraction job')
    response = REKOGNITION.get_text_detection(
        JobId=detection['JobId']
    )
    while(response['JobStatus'] == 'IN_PROGRESS'):
        sleep(1)
        response = REKOGNITION.get_text_detection(
        JobId=detection['JobId']
    )
    
    print('Matching brands')
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
                
            if detection['Timestamp'] != curr_timestamp and len(frames) > 0:
                es_results[curr_timestamp] = [
                    {
                        'brand': frame['MatchingBrands'][0][1],
                        'accuracy': frame['Confidence']*frame['MatchingBrands'][0][0]
                    }
                    for frame in frames
                ]
                batch.put_item(Item={
                    'S3Key': message['S3Key'],
                    'AttrType': 'ana/bft/'+str(message['SampleRate'])+'/{Timestamp}'.format(Timestamp=curr_timestamp),
                    'JobId': message['JobId'],
                    'DetectedLabels': dumps(frames)
                })
                frames = []
                curr_timestamp = detection['Timestamp']
            
            if len(matching_brands) > 0:
                frames.append({
                    'DetectedText': detection['TextDetection']['DetectedText'],
                    'Confidence': detection['TextDetection']['Confidence'],
                    'MatchingBrands': matching_brands,
                    'Geometry': detection['TextDetection']['Geometry']
                })
        if len(frames) > 0:
            es_results[curr_timestamp] = [
                    {
                        'brand': frame['MatchingBrands'][0][1],
                        'accuracy': frame['Confidence']*frame['MatchingBrands'][0][0]
                    }
                    for frame in frames
                ]
            batch.put_item(Item={
                'S3Key': message['S3Key'],
                'AttrType': 'ana/bft/{sample_rate}/{timestamp}'.format(
                    sample_rate=message['SampleRate'],
                    timestamp=curr_timestamp),
                'JobId': message['JobId'],
                'DetectedLabels': dumps(frames)
            })

    # Index documents on ElasticSearch
    ans = LAMBDA.invoke(
        FunctionName=environ['ES_LAMBDA_ARN'],
        InvocationType='RequestResponse',
        Payload=dumps({
            'results': es_results,
            'type': 'brands',
            'JobId': message['JobId'],
            'SampleRate': message['SampleRate'],
            'S3_Key': message['S3Key']
        })
    )
    print(ans)

    print ({
        'S3_Key': message['S3Key'],
        'AttrType': 'ana/bft/'+str(message['SampleRate'])+'/{Timestamp}'.format(Timestamp=curr_timestamp),
        'JobId': message['JobId'],
        'DetectedLabels': dumps(frames),
        'ESIndexResult': es_results
    })

    SNS_EMAIL_TOPIC = resource('sns').Topic(environ['SNS_EMAIL_TOPIC'])
    return SNS_EMAIL_TOPIC.publish(
        Message=" Brand from Text ready for S3Key: " + s3_key + " and JobId: " + JobId
    )
