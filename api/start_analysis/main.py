from json import dumps, loads
from os import environ
from re import compile

import boto3
from DynamoDBHelper import DynamoDBHelper

VIDEO_ANALYSIS_PATTERN = compile('/video_analysis')
VIDEO_ANALYSIS_UUID_PATTERN = compile('/video_analysis/[A-Za-z0-9-]*')


REGION = environ['AWS_REGION']
LAMBDA_FUNCTION_NAME = environ['START_ANALYSIS_FUNCTION']

lambda_client = boto3.client('lambda')


def handler(event, context):
    print("Processing event:\n"+dumps(event))

    response = {
        'isBase64Encoded':False,
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {
            'msg': "",
            'data': {}
        }
    }

    method = event['httpMethod']
    path = event['path']
    if method == 'POST' and VIDEO_ANALYSIS_PATTERN.fullmatch(path):
        body = loads(event['body'])
        print("Request Body: \n", body)
        response = post_video_analysis(body,response)
    elif method == 'GET' and VIDEO_ANALYSIS_PATTERN.fullmatch(path):
        response['body']['msg'] = "Video List"
    elif method == 'GET' and VIDEO_ANALYSIS_UUID_PATTERN.fullmatch(path):
        payload = dict(event['pathParameters'].items() | event['queryStringParameters'].items())
        response['body'] = get_video_analysis_by_uuid(payload,response)
    elif method is not 'GET' and method is not 'POST' :
        response["statusCode"] = 405
        response["body"][
            "msg"] = "Method not supported."
    else:
        response["statusCode"] = 404
        response["body"]["msg"] = "API Path not defined please validate you have the right resource path."

    return response

def validate_post_params(request):
    if 'file_path' not in request :
        print("Missing file_path on request")
        return False

    if 'video_analysis_list' not in request:
        print("Missing video_analysis_list on request")
        return False

    if 'sample_rate' not in request :
        print("Missing sample_rate on request")
        return False

    return True

def validate_get_by_uuid_params(request):
    if 'file_name' not in request:
        print("Missing file_name on request")
        return False

    if 'analysis_uuid' not in request:
        print("Missing analysis_uuid on path")
        return False

    return True

def post_video_analysis(payload,response):
    response_body = {}
    if validate_post_params(payload) is False:
        response["statusCode"] = 400
        response_body["msg"] = "Invalid request for path /video_analysis and method POST, validate " \
                                  "all parameters are present."
        response['body'] = dumps(response_body)
        return response

    try:
        lambda_response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',
            LogType='Tail',
            Payload= dumps(payload)
        )
    except Exception as e:
        print("Exception occurred while invoking lambda \n",e)
        response["statusCode"] = 500
        response_body["msg"] = "Exception occured while invoking lambda function."
        response['body'] = dumps(response_body)
        return response
    else:
        response_body["msg"] = "Video Analysis Job created succesfully"
        response_payload = loads(lambda_response['Payload'].read().decode())
        print("Response payload: \n",response_payload)
        response_body['data']  = response_payload['body']
        delimeter = '/'
        file_name = (payload['file_path'].split(delimeter)[-1])
        file_name_no_extension = file_name.split('.')[-2]
        response_body['data']['file_name']  = file_name_no_extension
        response["statusCode"] = response_payload['statusCode']
        response['body'] = dumps(response_body)

    return response

def get_video_analysis_by_uuid(payload,response):
    response_body = {}
    if validate_get_by_uuid_params(payload) is False:
        response["statusCode"] = 400
        response_body["msg"] = "Invalid request for path /video_analysis/{uuid} and method POST, " \
                                  "validate all parameters are present."
        response['body'] = dumps(response_body)
        return response

    uuid = payload['analysis_uuid']
    file_name = payload['file_name']
    dynamodb_helper = DynamoDBHelper(environ['DYNAMODB_TABLE_NAME'],REGION)
    primary_key = {
        "uuid": {
            "S": uuid
        },
        "file_name": {
            "S": file_name
        }
    }

    dynamo_response = dynamodb_helper.get_item(primary_key)
    if dynamo_response is False:
        response["statusCode"] = 404
        response_body["msg"] = "Video Analysis UUID not found"
        response['body'] = dumps(response_body)
    else:
        response_body["data"] = dynamo_response
        response_body["msg"] = "Video Analysis UUID results"
        response['body'] = dumps(response_body)

    return response
