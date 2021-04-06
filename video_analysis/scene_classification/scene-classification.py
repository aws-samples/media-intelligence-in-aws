from os import environ
from boto3 import client

region = environ['AWS_REGION']

# TODO
#   Handle job
#   Get results
#   Publish to SNS

def lambda_handler(event, context):

    response = {
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {}
    }

    print("Processing the event: \n ",event)

    if(validate_request_params(event) is False):
        response["statusCode"] = 400
        response["body"] = {"msg":"Missing parameters, please check your request"}
        return response

    # List bucket objects
    response['body'] = start_rekognition_label_job(event['frames_bucket'])


    return response

def start_rekognition_label_job(s3_bucket):
    rekognition_client = init_rekognition_client()

    if rekognition_client is False:
        raise Exception("Rekognition client creation failed")

    # TODO
    #   Add S3 client
    #   List objects
    #   Foreach jpg or png file in bucket analyze it 

    try:
        job_response = rekognition_client.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': 'globo-dev',
                    'Name': 'videos/analysis/360p-amor-de-m-e/360p-amor-de-m-e_frame_.0000007.jpg'
                }
            },
            MaxLabels=100
        )
    except Exception as e:
        print("Rekognition job creation exception \n", e)
        return False
    else:
        print(job_response)

    return True


def validate_request_params(request):
    if("frames_bucket" not in request):
        print("file_path not found on request \n")
        return False

    return True

def init_rekognition_client():

    try:
        rekognition_client = client("rekognition", region_name=region)
    except Exception as e:
        print("An error occurred while initializing RekognitionClient \n", e)
        return False

    return rekognition_client




