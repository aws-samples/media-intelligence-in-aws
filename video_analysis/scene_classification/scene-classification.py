from os import environ
from boto3 import client

region = environ['AWS_REGION']

# TODO
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
    response['body'] = start_rekognition_label_job(event['frames_bucket'],event['frames_folder'])


    return response

def start_rekognition_label_job(s3_bucket,analysis_path,min_confidence=0.7,name_identifier="_frame_"):
    s3_client = init_boto3_client('s3')
    rekognition_client = init_boto3_client('rekognition')

    if s3_client is False:
        raise Exception("S3 client creation failed")

    s3_objects = get_s3_object_list(s3_client,s3_bucket,analysis_path)

    if(s3_objects is False):
        print("Empty folder "+analysis_path+" on bucket "+s3_bucket+" task aborted")
        return {"msg":"Empty folder "+analysis_path+" on bucket "+s3_bucket+" task aborted"}

    object_name_list = process_s3_object_list(s3_objects)
    if (len(object_name_list) <= 0):
        print("No frames found on " + analysis_path + " on bucket " + s3_bucket + ", verify your MediaConvert job, only jpg and png files supported")
        return {"msg": "No frames found verify your MediaConvert job, only jpg and png files supported"}

    if rekognition_client is False:
        raise Exception("Rekognition client creation failed")


    # TODO
    #   Store the results somewhere
    analysis_results = []
    for file_name in object_name_list:
        try:
            job_response = rekognition_client.detect_labels(
                Image={
                    'S3Object': {
                        'Bucket': s3_bucket,
                        'Name': file_name
                    }
                },
                MaxLabels=10,
                MinConfidence=min_confidence
            )
        except Exception as e:
            print("Rekognition job creation exception on file: "+file_name+" \n", e)
            return {"msg": "Rekognition job creation exception, review logs for more information"}
        else:
            result_base = {
                "file":file_name,
                "rekognition_detect_labels_result":job_response
            }
            analysis_results.append(result_base.copy())

    return {"msg": "Job completed for "+str(len(object_name_list))+" frames","data":analysis_results}


def validate_request_params(request):
    if("frames_bucket" not in request):
        print("frames_bucket not found on request \n")
        return False

    if("frames_folder" not in request):
        print("frames_folder not found on request \n")
        return False

    return True

def init_boto3_client(client_type="s3"):
    try:
        custom_client = client(client_type, region_name=region)
    except Exception as e:
        print("An error occurred while initializing "+client_type.capitalize()+"Client \n", e)
        return False

    return custom_client

def get_s3_object_list(s3_client,s3_bucket,path,marker=''):
    s3_objects = []
    try:
        if marker == '':
            s3_response = s3_client.list_objects(
                Bucket=s3_bucket,
                Delimiter='/',
                EncodingType='url',
                MaxKeys=1000,
                Prefix=path
            )
        else:
            s3_response = s3_client.list_objects(
                Bucket=s3_bucket,
                Marker=marker,
                Delimiter='/',
                EncodingType='url',
                MaxKeys=1000,
                Prefix=path
            )
    except Exception as e:
        print("An error occured while listing objects from bucket: "+s3_bucket+" \n",e)
        return False
    else:
        if s3_response['IsTruncated']:
            s3_objects = s3_objects + get_s3_object_list(s3_client,s3_bucket,path,s3_response['NextMarker'])
        else:
            s3_objects = s3_objects + s3_response['Contents']

    return s3_objects

def process_s3_object_list(s3_objects_list,name_identifier="_frame_"):
    object_name_list = []
    for s3_object in s3_objects_list:
        if (".jpg" in s3_object['Key'] or ".png" in s3_object['Key']) and name_identifier in s3_object['Key']:
            object_name_list.append(s3_object['Key'])

    return object_name_list



