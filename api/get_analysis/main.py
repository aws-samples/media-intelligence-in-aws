from os import environ
from json import dumps,loads
from boto3 import resource
from boto3.dynamodb.conditions import Key

DDB = resource('dynamodb')
TABLE = DDB.Table(environ['DDB_TABLE'])

RESPONSE_PATTERN = {
    'isBase64Encoded':False,
    'headers': {
    'Access-Control-Allow-Origin': '*'
    }
}

def lambda_handler(event, context):
    s3_key = event['queryStringParameters'].get('s3_key', None) if event['queryStringParameters'] else None
    uuid = event['queryStringParameters'].get('uuid', None) if event['queryStringParameters'] else None
    
    print('Processing event:\n'+dumps(event))
    body = get_video_analysis_by_uuid(uuid, s3_key)
    RESPONSE_PATTERN.update(body)
    
    print('Response:\n', body)
    return dumps(RESPONSE_PATTERN)

def get_video_analysis_by_uuid(uuid, s3_key):
    primary_key = {
        'S3_KEY': 'test/key.mp4',
        'ATTR_TYPE': 'ana/brand-text/1234'
    }
    
    dynamo_response = TABLE.get_item(Key=primary_key)
    dynamo_response = TABLE.query(
        KeyConditionExpression = 
            Key('S3_KEY').eq(primary_key['S3_KEY']) & Key('ATTR_TYPE').begins_with('ana')
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
