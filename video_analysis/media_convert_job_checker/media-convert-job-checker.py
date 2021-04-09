from os import environ
from boto3 import client
from json import dumps

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

    print("Processing the event: \n ",dumps(event))

    if(validate_request_params(event) is False):
        response["statusCode"] = 400
        response["body"] = {"msg":"Missing parameters, please check your request"}
        return response

    sns_custom_payload = event['Records'][0]['Sns']['Message']
    sns_custom_payload = sns_custom_payload.replace("job_id:","")
    sns_custom_payload = sanitize_string(sns_custom_payload)

    job_response = check_mediaconvert_job(sns_custom_payload)


    if(job_response is False):
        response["statusCode"] = 500
        response["body"] = {"msg": "Failed getting MediaConvertJob refer to the logs for more details"}
        return response

    write_to_dynamodb = write_mediaconvert_status_to_dynamodb(job_response)
    if write_to_dynamodb is not False:
        response['body']['dynamodb_update'] = True
    else:
        response['body']['dynamodb_update'] = False

    response["body"]["msg"] = "MediaConvert Job "+job_response["id"]+" status retreived"

    response["body"]["job_id"] = job_response["id"]

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

def dynamodb_search_by_mediaconvert_jobid(dynamodb_client,job_id):
    try:
        dynamo_search_response = dynamodb_client.query(
            TableName=environ['DYNAMODB_TABLE_NAME'],
            Select='ALL_ATTRIBUTES',
            ConsistentRead=True,
            KeyConditionExpression="mediaconvert_job_id = :mediaconvert_job_id",
            ExpressionAttributeValues={
                ':mediaconvert_job_id': {'S': job_id}
            }
        )
    except Exception as e:
        print("Exception while getting item from DynamoDB \n",e)
        return False
    else:
        if(len(dynamo_search_response['Items']) <= 0):
            print("No item found with mediaconvert_job_id: "+job_id)
            return False
        return dynamo_search_response['Items'][0]

def write_mediaconvert_status_to_dynamodb(mediaconvert_job):
    dynamodb_client = init_boto3_client("dynamodb")
    if dynamodb_client is False:
        raise Exception("MediaConvert client creation failed")

    dynamodb_record = dynamodb_search_by_mediaconvert_jobid(dynamodb_client,mediaconvert_job['id'])
    print("Dynamo record: \n",dynamodb_record)
    if(dynamodb_record is False):
        print("No data found for mediaconvert job_id, verify the record exist on dynamodb")
        return False

    return False

def write_video_record_dynamodb(key,update_expression):
    dynamodb_client = init_boto3_client("dynamodb")
    if dynamodb_client is False:
        raise Exception("MediaConvert client creation failed")
    try:
        dynamo_response = dynamodb_client.update_item(
            TableName=environ['DYNAMODB_TABLE_NAME'],
            Key={
                "uuid":{
                    "S":key
                }
            },
            UpdateExpression=update_expression
        )
    except Exception as e:
        print("Exception while writing item to DynamoDB \n",e)
        return False
    else:
        assigned_uuid = ""

    return True

def sanitize_string(string_variable):
    string_variable=string_variable.replace("\n","")
    string_variable = string_variable.replace("\"","")
    string_variable = string_variable.replace("\'","")
    string_variable = string_variable.replace("\r","")
    string_variable = string_variable.replace(":","")
    return string_variable

def publish_to_sns(message):
    return False

def init_boto3_client(client_type="s3"):
    try:
        custom_client = client(client_type, region_name=region)
    except Exception as e:
        print("An error occurred while initializing "+client_type.capitalize()+"Client \n", e)
        return False

    return custom_client