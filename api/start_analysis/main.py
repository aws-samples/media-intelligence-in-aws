from os import environ
from json import dumps,loads
from re import compile
import boto3

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
    body = loads(event['body'])

    print("Request Body: \n",body)

    if method == 'POST' and VIDEO_ANALYSIS_PATTERN.fullmatch(path):
        response = post_video_analysis(body,response)
    elif method == 'GET' and VIDEO_ANALYSIS_PATTERN.fullmatch(path):
        response['body']['msg'] = "Video List"
    elif method == 'GET' and VIDEO_ANALYSIS_UUID_PATTERN.fullmatch(path):
        response['body']['msg'] = "Video Analysis UUID"
    elif method is not 'GET' and method is not 'POST' :
        response["statusCode"] = 405
        response["body"][
            "msg"] = "Method not supported."
    else:
        response["statusCode"] = 404
        response["body"]["msg"] = "API Path not defined please validate you have the right resource path."

    return response

def validate_params(request):
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

def post_video_analysis(payload,response):
    if validate_params(payload) is False:
        response["statusCode"] = 400
        response["body"]["msg"] = "Invalid request for path /video_analysis and method POST, validate all parameters are present."
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
        response["body"]["msg"] = "Exception occured while invoking lambda function."
        return response
    else:
        response['body']['msg']  = "Video Analysis Job created succesfully"
        response['body']['data']  = lambda_response['Payload'].read()

    return response
# /*
# * endpoint: { s3_path, analysis_list,sample_rate}
# * endpoint: {uuid, status_job, outputbucket}
# * endpoint: {uuid, status_for_each_analysis}
# * policies for each lambda
# * */
