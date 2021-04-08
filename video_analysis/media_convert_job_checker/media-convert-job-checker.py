from os import environ
from boto3 import client
import json

region = environ['AWS_REGION']

# TODO
#   Handle job
#   Rename frames to use timestamp
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

    sns_custom_payload = event['Records'][0]['Sns']['Message']
    print(sns_custom_payload)
    sns_custom_payload_json = json.load(sns_custom_payload)

    job_response = check_mediaconvert_job(sns_custom_payload_json['job_id'])

    if(job_response is False):
        response["statusCode"] = 500
        response["body"] = {"msg": "Failed getting MediaConvertJob refer to the logs for more details"}
        return response

    response["body"]["msg"] = "MediaConvert Job "+event["job_id"]+" status retreived"
    response["body"]["job_id"] = event["job_id"]
    response["body"]["job_response"] = job_response

    # TODO
    #   Process the frame files to add timestamp depending on frame rate
    rename_result = 0

    return response

def check_mediaconvert_job(job_id):
    mc_client = init_media_convert_client()

    if mc_client is False:
        raise Exception("MediaConvert client creation failed")

    try:
        job_response = mc_client.get_job(
            Id=job_id
        )
    except Exception as e:
        print("MediaConvert get job exception \n", e)
        return False
    else:
        try:
            job_json = job_response['Job']
            job = {
                "id": job_json['Id'],
                "status": job_json['Status'],
                "messages": job_json['Messages'],
                "outputgroup_details": job_json['OutputGroupDetails'],
                "output_bucket_path": job_json['Settings']['OutputGroups'][0]['OutputGroupSettings']['FileGroupSettings']['Destination']
            }
            for output_group in job_json['Settings']['OutputGroups']:
                if output_group['ContainerSettings']['Container'] == "RAW":
                    numerator = output_group['VideoDescription']['CodecSettings']['FramerateNumerator']
                    denominator = output_group['VideoDescription']['CodecSettings']['FramerateDenominator']
                    job['sample_rate'] = numerator/denominator
        except Exception as e:
            print("Parsing Job Exception \n",e)
            return False

    return job


def validate_request_params(request):
    if("job_id" not in request['Records'][0]['Sns']['Message']):
        print("job_id not found on request \n")
        return False

    return True

def init_media_convert_client():
    if ("MEDIACONVERT_ENDPOINT" in environ):
        mediaconvert_endpoint = environ["MEDIACONVERT_ENDPOINT"]
        mediaconvert_client = client("mediaconvert", region_name=region, endpoint_url=mediaconvert_endpoint)
    else:
        try:
            mediaconvert_client = client("mediaconvert", region_name=region)
            response = mediaconvert_client.describe_endpoints()
        except Exception as e:
            print("An error occurred while listing MediaConvert endpoints \n", e)
            return False
        else:
            mediaconvert_endpoint = response["Endpoints"][0]["Url"]
            # Cache the mediaconvert endpoint in order to avoid getting throttled on
            # the DescribeEndpoints API.
            environ["MEDIACONVERT_ENDPOINT"] = mediaconvert_endpoint
            mediaconvert_client = client("mediaconvert", region_name=region, endpoint_url=mediaconvert_endpoint)

    return mediaconvert_client

def rename_frames_to_timestamp(name_modifier="_frame_"):
    # List frame objects, create pattern, update s3 files
    return True

def init_boto3_client(client_type="s3"):
    try:
        custom_client = client(client_type, region_name=region)
    except Exception as e:
        print("An error occurred while initializing "+client_type.capitalize()+"Client \n", e)
        return False

    return custom_client