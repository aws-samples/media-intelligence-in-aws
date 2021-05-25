from os import environ
from json import dumps,loads
from boto3 import resource
from boto3.dynamodb.conditions import Key

TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
ANALYSIS_LIST = environ['ANALYSIS_LIST']

RESPONSE_PATTERN = {
    'isBase64Encoded':False,
    'headers': {
    'Access-Control-Allow-Origin': '*'
    }
}

def lambda_handler(event, context):
    s3_key = event['queryStringParameters'].get('s3_key', None) if event['queryStringParameters'] else None
    job_id = event['queryStringParameters'].get('jobid', None) if event['queryStringParameters'] else None
    analysis = event['queryStringParameters'].get('analysis', None) if event['queryStringParameters'] else None

    print('Processing event:\n'+dumps(event))
    print(ANALYSIS_LIST)
    #body = get_video_analysis_by_uuid(uuid, s3_key)
    #RESPONSE_PATTERN.update(body)
    
    #print('Response:\n', body)
    return dumps(RESPONSE_PATTERN)

def get_video_analysis_by_uuid(uuid, s3_key):
    primary_key = {
        'S3_KEY': 'test/key.mp4',
        'ATTR_TYPE': 'ana/brand-text/1234'
    }

    dynamo_response = TABLE.query(
        KeyConditionExpression = 
            Key('S3_KEY').eq(primary_key['S3_KEY']) & Key('ATTR_TYPE').between('ana/0000000/0','ana/zzzzzzzz/100')
    )

    print(dynamo_response['Items'])
    print('------')
    return {
        'statusCode': 200,
        'body': {
            'msg': 'results',
            'data': dynamo_response['Items']
        }
    }

def get_analysis_dynamo_results(s3_key,analysis_base_name):
    osc_results = TABLE.query(
        KeyConditionExpression=
        Key('S3Key').eq(s3_key) & Key('AttrType').begins_with(analysis_base_name + "0")
    )['Items']
    all_results = []
    i = 0
    while i < 10:
        for result in osc_results:
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