from os import environ
from boto3 import client
from json import dumps,loads
from HelperLibrary.DynamoDBHelper.DynamoDBHelper import DynamoDBHelper
from HelperLibrary.BaseHelper import BaseHelper
from time import time


region = environ['AWS_REGION']
anylisis_name = environ['ANALYSIS_NAME']
all_anylisis_flag = environ['ALL_ANALYSIS_NAME']

def lambda_handler(event, context):

    response = {
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': {}
    }

    print("Processing the event: \n ", dumps(event))

    if (validate_request_params(event) is False):
        response["statusCode"] = 400
        response["body"] = {"msg": "Missing parameters, please check your request"}
        return response

    sns_subject = event['Records'][0]['Sns']['Subject']
    if(anylisis_name not in sns_subject and all_anylisis_flag  not in sns_subject):
        response["statusCode"] = 400
        response["body"] = {"msg": "Wrong analysis flag name in: "+sns_subject}
        return response

    sns_message = event['Records'][0]['Sns']['Message']
    sns_message_json = loads(loads(sns_message))


    # TODO
    #   Save results per object
    #   Update analysis status
    #   Publish to sns completition
    dynamo_helper = DynamoDBHelper(environ['DYNAMODB_TABLE_NAME'], region)
    primary_key_structure = {
        "uuid": {
            'S': sanitize_string(sns_message_json["uuid"])
        },
        "file_name": {
            'S': sns_message_json['file_name']
        }
    }

    dynamo_record = dynamo_helper.get_item(primary_key_structure)
    if(dynamo_record is False):
        print("No record found on DynamoDB for key: \n",dumps(primary_key_structure))
        response["statusCode"] = 404
        response["body"] = {"msg": "No record found on DynamoDB"}
        return response

    update_expression, attributes_values = dynamo_helper.build_update_expression("scene_classification_status", "STARTED","S")
    write_to_dynamodb = dynamo_helper.update_dynamodb_item(primary_key_structure, update_expression, attributes_values)
    if write_to_dynamodb is not False:
        response['body']['dynamodb_scene_classification_update'] = True
    else:
        response['body']['dynamodb_scene_classification_update'] = False

    # TODO
    #  Handle DLQ
    if('item_offset' in sns_message_json):
        response["body"] = continue_scene_classification_job(dynamo_helper,dynamo_record,sns_message_json['item_offset'])

    start_time = time()
    scene_classification_result = start_rekognition_label_job(dynamo_helper,dynamo_record)
    end_time = time()
    scene_classification_result['elapsed_time'] = str(end_time - start_time)
    update_expression = ""
    attributes_values = {}

    if(scene_classification_result == False):
        response['body']['msg'] = "Failed scene classification task, view logs for further information"
        scene_classification_status = "ERROR"
    else:
        scene_classification_status = "COMPLETED"
        update_expression, attributes_values = dynamo_helper.build_update_expression("scene_classification_results",
                                                                                     dumps(scene_classification_result), "S",update_expression,attributes_values)

    update_expression, attributes_values = dynamo_helper.build_update_expression("scene_classification_status",
                                                                                 scene_classification_status, "S",update_expression,attributes_values)

    write_to_dynamodb = dynamo_helper.update_dynamodb_item(primary_key_structure, update_expression, attributes_values)
    if write_to_dynamodb is False:
        print("Failed to update job status to DynamoDB")

    return response

def start_rekognition_label_job(dynamo_helper,dynamo_record,min_confidence=70,name_identifier="_frame_"):
    response = {}
    base_helper = BaseHelper("Helper")
    s3_client = base_helper.init_boto3_client('s3',region)
    rekognition_client = base_helper.init_boto3_client('rekognition',region)

    if s3_client is False:
        raise Exception("S3 client creation failed")


    delimeter = '/'
    s3_bucket = delimeter.join(dynamo_record['mediaconvert_job_output_bucket']['S'].split(delimeter)[2:3])
    analysis_path = delimeter.join(dynamo_record['mediaconvert_job_output_bucket']['S'].split(delimeter)[3:-1])+"/"
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
    failed_frames = []
    total_images = len(object_name_list)
    current_frame = 0
    primary_key_structure = {
        "uuid": dynamo_record['uuid'],
        "file_name": dynamo_record['file_name']
    }
    for file_name in object_name_list:
        start_time = time()
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
            failed_frames.append({'frame_name':file_name,'reason':e})
        else:
            end_time = time()
            result_base = {
                "file":file_name,
                "rekognition_detected_labels":job_response['Labels'],
                "processing_time":end_time-start_time
            }
            analysis_results.append(result_base.copy())

        progress = current_frame*100/total_images
        update_expression, attributes_values = dynamo_helper.build_update_expression("scene_classification_progress",
                                                                                     str(progress), "S")
        updated_to_dynamodb = dynamo_helper.update_dynamodb_item(primary_key_structure, update_expression,
                                                               attributes_values)

        if(updated_to_dynamodb == False):
            print("Error while updating progress to DynamoDB")

        current_frame += 1


    response['msg'] = "Job completed for "+str(len(object_name_list))+" frames"
    response["frames_result"] = analysis_results
    response["frames_failed"] = failed_frames

    return response


def validate_request_params(request):
    if('Sns' not in request['Records'][0]):
        print("No SNS message")
        return False
    if(request['Records'][0]['Sns']['Message'] == ""):
        print("No message found on request \n")
        return False
    if (request['Records'][0]['Sns']['Subject'] == ""):
        print("No subject on request \n")
        return False
    return True

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

def sanitize_string(string_variable):
    string_variable=string_variable.replace("\n","")
    string_variable = string_variable.replace("\"","")
    string_variable = string_variable.replace("/","")
    string_variable = string_variable.replace("\'","")
    string_variable = string_variable.replace("\r","")
    string_variable = string_variable.replace(":","")
    return string_variable

def continue_scene_classification_job(dynamo_helper,dynamo_record,item_offset):
    return False
