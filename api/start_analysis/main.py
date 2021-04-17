from os import environ
from json import dumps,loads
import boto3

REGION = environ['AWS_REGION']
LAMBDA_FUNCTION_NAME = environ['START_ANALYSIS_FUNCTION']

lambda_client = boto3.client('lambda')


def handler(event, context):
    print("Processing event:\n"+dumps(event))

    response = {
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {
            'msg': "",
            'data': {}
        }
    }

    if(validate_params(event) is False):
        response["statusCode"] = 400
        response["body"]["msg"] = "Invalid request, validate all parameters are present."
        return response


    try:
        lambda_response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',
            LogType='Tail',
            Payload= event
        )
    except Exception as e:
        print("Exception occurred while invoking lambda \n",e)
        response["statusCode"] = 500
        response["body"]["msg"] = "Exception occured while invoking lambda function."
        return response
    else:
        response['body'] = lambda_response

    return response


def validate_params(request):
    if('s3_path' not in request):
        print("Missing s3_path on request")
        return False

    if('analysis_list' not in request):
        print("Missing analysis_list on request")
        return False

    if('sample_rate' not in request):
        print("Missing sample_rate on request")
        return False

    return True


# /*
# * endpoint: { s3_path, analysis_list,sample_rate}
# * endpoint: {uuid, status_job, outputbucket}
# * endpoint: {uuid, status_for_each_analysis}
# * policies for each lambda
# * */