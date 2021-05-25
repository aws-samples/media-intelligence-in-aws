from os import environ
from json import dumps,loads
from boto3.dynamodb.conditions import Key
from AudioFrameExtractor import AudioFrameExtractor
from boto3 import resource
import time

TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
AFE = AudioFrameExtractor(
    role_arn=environ['MEDIA_CONVERT_ARN'],
    destination_bucket = environ['DEST_S3_BUCKET']
)
SNS_TOPIC = resource('sns').Topic(environ['SNS_TOPIC'])

RESPONSE_PATTERN = {
    'isBase64Encoded':False,
    'headers': {
    'Access-Control-Allow-Origin': '*'
    },
    'body':{}
}

# StartAnalysis [POST] (analysis/start)

def lambda_handler(event, context):
    print('Processing event:\n'+dumps(event))
    print('---')
    event['body'] = loads(event['body'])
    print('Request Body: \n', event['body'])
    try:
        ignore = event['body'].pop('IgnoreExtract')
    except KeyError:
        ignore = False

    if 'SampleRate' not in event['body']:
        event['body']['SampleRate'] = 1

    previous_extraction = had_previous_extraction(event['body']['S3Key'], event['body']['SampleRate'])
    if ((len(previous_extraction) <= 0) or ignore):
        # Video has not been extrated yet. Proceed to extraction
        event = start_new_analysis(event)
        TABLE.put_item(
            Item=event['body']
        )
    else:
        # Video has already been extracted
        Item = previous_extraction[0]
        print(Item)
        mc_job = AFE.get_mediaconvert_job(Item['JobId'])['Job']
        if mc_job is False:
            print("No MediaConvert Job found for the dynamo record")
            event = start_new_analysis(event)
            TABLE.put_item(
                Item=event['body']
            )
        else:
            event['timestamp'] = time.time()
            event['body']['JobId'] = Item['JobId']
            event['body']['AttrType'] = Item['AttrType']
            event['body']['Status'] = 'SUBMITTED'
            SNS_TOPIC.publish(
                Message=dumps(
                    {
                        "S3Key": Item['S3Key'],
                        "JobId": Item['JobId'],
                        "SampleRate": event['body']['SampleRate'],
                        "OutputPath": mc_job['Settings']['OutputGroups'][0]['OutputGroupSettings']['FileGroupSettings']['Destination']
                    }
                ),
                MessageAttributes={
                    'analysis': {
                        'DataType': 'String.Array',
                        'StringValue': dumps(Item['analysis'])
                    }
                }
            )

    RESPONSE_PATTERN['body'] = dumps(event['body'])
    return (RESPONSE_PATTERN)


def had_previous_extraction(s3_key, sample_rate):
    return TABLE.query(
            KeyConditionExpression = 
                Key('S3Key').eq(s3_key) & Key('AttrType').eq(f'frm/{sample_rate}')
        )['Items']

def start_new_analysis(event):
    timestamp = time.time()
    event['timestamp'] = timestamp
    event['body']['JobId'] = AFE.start_mediaconvert_job(
        S3Key='s3://{bucket}/{key}'.format(bucket=environ['IN_S3_BUCKET'], key=event['body']['S3Key']),
        SampleRate=event['body']['SampleRate'],
        Timestamp=timestamp
    )
    event['body']['AttrType'] = 'frm/{SampleRate}'.format(SampleRate=event['body']['SampleRate'])
    event['body']['Status'] = 'SUBMITTED'

    return event