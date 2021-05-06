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
# SNS_TOPIC = resource('sns').Topic(environ['SNS_TOPIC_TEST'])

RESPONSE_PATTERN = {
    'isBase64Encoded':False,
    'headers': {
    'Access-Control-Allow-Origin': '*'
    }
}

# GetAnalysis [GET] (analysis/{s3key}?Param1=bla)
# StartAnalysis [POST] (analysis/start)

def lambda_handler(event, context):
    print('Processing event:\n'+dumps(event))
    print('---')
    # body = loads(event['body'])
    print('Request Body: \n', event['body'])

    try:
        ignore = event['body'].pop('IgnoreExtract')
    except KeyError:
        ignore = False

    if 'SampleRate' not in event['body']:
        event['body']['SampleRate'] = 1

    if (not had_previous_extraction(event['body']['S3Key'], event['body']['SampleRate']) or 
        ignore): 
        # Video has not been extrated yet. Proceed to extraction
        timestamp = time.time()
        event['timestamp'] = timestamp
        event['body']['JobId'] = AFE.start_mediaconvert_job(
            S3Key='s3://{bucket}/{key}'.format(bucket=environ['IN_S3_BUCKET'], key=event['body']['S3Key']),
            SampleRate=event['body']['SampleRate'],
            Timestamp=timestamp
        )
        event['body']['AttrType'] = 'frm/{SampleRate}'.format(SampleRate=event['body']['SampleRate'])
        event['body']['Status']: 'SUBMITTED'
        TABLE.put_item(
            Item=event['body']
        )
    else:
        # TODO: POST MESSAGE ON TOPIC DIRECTLY
        print('Job already exists')
        # return SNS_TOPIC.publish(
        #     Message=dumps(
        #         {
        #             "S3Key": Item['S3Key'],
        #             "JobId": JobId,
        #             "OutputPath": mc_job['Settings']['OutputGroups'][0]['OutputGroupSettings']['FileGroupSettings']['Destination']
        #         }
        #     ),
        #     MessageAttributes={
        #         'analysis': {
        #             'DataType': 'String.Array',
        #             'StringValue': dumps(Item['analysis'])
        #         }
        #     }
        # )

    RESPONSE_PATTERN.update(event['body'])
    return dumps(RESPONSE_PATTERN)


def had_previous_extraction(s3_key, sample_rate):
    return len(
        TABLE.query(
            KeyConditionExpression = 
                Key('S3Key').eq(s3_key) & Key('AttrType').eq(f'frm/{sample_rate}')
        )['Items']
    ) > 0

# def validate_post_params(request):
#     if 'file_path' not in request :
#         print('Missing file_path on request')
#         return False

#     if 'video_analysis_list' not in request:
#         print('Missing video_analysis_list on request')
#         return False

#     if 'sample_rate' not in request :
#         print('Missing sample_rate on request')
#         return False

#     return True
