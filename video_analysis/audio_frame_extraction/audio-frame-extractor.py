from os import environ
from boto3 import client
import uuid

mediaconvert_role = environ['MEDIACONVERT_ROLE']
destination_bucket = environ['MEDIACONVERT_DESTINATION_BUCKET']
region = environ['AWS_REGION']

# TODO
#   Write to DynamoDB Table

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

    job_id = start_mediaconvert_job(event["file_path"],event["sample_rate"])

    if(job_id is False):
        response["statusCode"] = 500
        response["body"] = {"msg": "Failed creating MediaConvertJob refer to the logs for more details"}
        return response

    response["body"]["msg"] = "MediaConvert Job succesfully created"
    response["body"]["job_id"] = job_id

    file_name = (event["file_path"].split('/')[-1])
    file_name_no_extension = file_name.split('.')[-2]

    write_to_dynamodb = write_video_record_dynamodb(file_name_no_extension,job_id,event["sample_rate"],event["video_analysis_list"])
    if write_to_dynamodb is not False:
        response['body']['dynamodb_write'] = True
    else:
        response['body']['dynamodb_write'] = False

    return response

def start_mediaconvert_job(s3_key,sample_rate):
    mc_client = init_media_convert_client()

    if mc_client is False:
        raise Exception("MediaConvert client creation failed")

    settings = build_media_convert_job_settings(s3_key,sample_rate)
    try:
        job_response = mc_client.create_job(
            Role=mediaconvert_role,
            Settings=settings
        )
    except Exception as e:
        print("MediaConvert job creation exception \n", e)
        return False
    else:
        job_id = job_response['Job']['Id']

    return job_id


def validate_request_params(request):
    if("file_path" not in request):
        print("file_path not found on request \n")
        return False
    if("sample_rate" not in request):
        print("sample_rate not found on request \n")
        return False
    if ("video_analysis_list" not in request):
        print("video_analysis_list not found on request \n")
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

def build_media_convert_job_settings(s3_key,sample_rate = 1):

    delimeter = '/'
    destination_bucket_uri = "s3://"+destination_bucket+"/videos/analysis/"

    file_name = (s3_key.split(delimeter)[-1])
    file_name_no_extension = file_name.split('.')[-2]

    #Always a video required as an output for MediaConvert
    base_video_output = {
        "ContainerSettings":{
            "Container": "MP4",
            "Mp4Settings": {
                "CslgAtom": "INCLUDE",
                "CttsVersion": 0,
                "FreeSpaceBox": "EXCLUDE",
                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
            }
        },
        "VideoDescription": {
            "ScalingBehavior": "DEFAULT",
            "TimecodeInsertion": "DISABLED",
            "AntiAlias": "ENABLED",
            "Sharpness": 50,
            "CodecSettings": {
                "Codec": "H_264",
                "H264Settings": {
                    "InterlaceMode": "PROGRESSIVE",
                    "NumberReferenceFrames": 3,
                    "Syntax": "DEFAULT",
                    "Softness": 0,
                    "GopClosedCadence": 1,
                    "GopSize": 90,
                    "Slices": 1,
                    "GopBReference": "DISABLED",
                    "SlowPal": "DISABLED",
                    "EntropyEncoding": "CABAC",
                    "Bitrate": 10000,
                    "FramerateControl": "INITIALIZE_FROM_SOURCE",
                    "RateControlMode": "CBR",
                    "CodecProfile": "MAIN",
                    "Telecine": "NONE",
                    "MinIInterval": 0,
                    "AdaptiveQuantization": "AUTO",
                    "CodecLevel": "AUTO",
                    "FieldEncoding": "PAFF",
                    "SceneChangeDetect": "ENABLED",
                    "QualityTuningLevel": "SINGLE_PASS",
                    "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                    "UnregisteredSeiTimecode": "DISABLED",
                    "GopSizeUnits": "FRAMES",
                    "ParControl": "INITIALIZE_FROM_SOURCE",
                    "NumberBFramesBetweenReferenceFrames": 2,
                    "RepeatPps": "DISABLED",
                    "DynamicSubGop": "STATIC"
                }
            },
            "AfdSignaling": "NONE",
            "DropFrameTimecode": "ENABLED",
            "RespondToAfd": "NONE",
            "ColorMetadata": "INSERT"
        },
        "AudioDescriptions": [
            {
                "AudioTypeControl": "FOLLOW_INPUT",
                "AudioSourceName": "Audio Selector 1",
                "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                        "AudioDescriptionBroadcasterMix": "NORMAL",
                        "Bitrate": 96000,
                        "RateControlMode": "CBR",
                        "CodecProfile": "LC",
                        "CodingMode": "CODING_MODE_2_0",
                        "RawFormat": "NONE",
                        "SampleRate": 48000,
                        "Specification": "MPEG4"
                    }
                },
                "LanguageCodeControl": "FOLLOW_INPUT"
            }
        ],
        "Extension": "mp3",
        "NameModifier": "_audio"
    }

    sample_rate_numerator,sample_rate_denominator = convert_float_to_fraction(sample_rate)

    base_framing_output = {
        "ContainerSettings": {
            "Container": "RAW"
        },
        "VideoDescription": {
            "ScalingBehavior": "DEFAULT",
            "TimecodeInsertion": "DISABLED",
            "AntiAlias": "ENABLED",
            "Sharpness": 50,
            "CodecSettings": {
                "Codec": "FRAME_CAPTURE",
                "FrameCaptureSettings": {
                    "FramerateNumerator": sample_rate_numerator,
                    "FramerateDenominator": sample_rate_denominator,
                    "MaxCaptures": 10000000,
                    "Quality": 100
                }
            },
            "DropFrameTimecode": "ENABLED",
            "ColorMetadata": "INSERT"
        },
        "NameModifier": "_frame_"
    }
    base_audio_output = {
        "ContainerSettings": {
            "Container": "MP4",
            "Mp4Settings": {
                "CslgAtom": "INCLUDE",
                "CttsVersion": 0,
                "FreeSpaceBox": "EXCLUDE",
                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
            }
        },
        "AudioDescriptions": [
            {
                "AudioTypeControl": "FOLLOW_INPUT",
                "AudioSourceName": "Audio Selector 1",
                "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                        "AudioDescriptionBroadcasterMix": "NORMAL",
                        "Bitrate": 96000,
                        "RateControlMode": "CBR",
                        "CodecProfile": "LC",
                        "CodingMode": "CODING_MODE_2_0",
                        "RawFormat": "NONE",
                        "SampleRate": 48000,
                        "Specification": "MPEG4"
                    }
                },
                "LanguageCodeControl": "FOLLOW_INPUT"
            }
        ]
    }
    output_group = {
        "CustomName": "",
        "Name": "File Group",
        "Outputs": [
            base_video_output,
            base_audio_output,
            base_framing_output
        ],
        "OutputGroupSettings": {
            "Type": "FILE_GROUP_SETTINGS",
            "FileGroupSettings": {
                "Destination": destination_bucket_uri+file_name_no_extension+"/"
            }
        }
    }
    base_input = {
        "AudioSelectors": {
            "Audio Selector 1": {
                "Offset": 0,
                "DefaultSelection": "DEFAULT",
                "ProgramSelection": 1
            }
        },
        "VideoSelector": {
            "ColorSpace": "FOLLOW"
        },
        "FilterEnable": "AUTO",
        "PsiControl": "USE_PSI",
        "FilterStrength": 0,
        "DeblockFilter": "DISABLED",
        "DenoiseFilter": "DISABLED",
        "TimecodeSource": "EMBEDDED",
        "FileInput": ""
    }

    base_settings = {
        "Inputs": [],
        "OutputGroups": [output_group]
    }

    base_input["FileInput"] = s3_key
    base_settings["Inputs"].append(base_input.copy())

    return base_settings


def convert_float_to_fraction(number, decimal_separator='.'):
    denominator = 1

    if (type(number) is float):
        if (float(number).is_integer() is False):
            number = str(number)
            decimal_point = number.find(decimal_separator)
            if (decimal_separator != -1):
                denominator = int(pow(10, (len(number) - 1 - decimal_point)))
                numerator = int(number.replace(decimal_separator, ''))
        else:
            numerator = int(number)
    else:
        numerator = int(number)

    return numerator, denominator

def write_video_record_dynamodb(video_name,job_id,sample_rate=1,video_analysis_list=["ALL_AVAILABLE"]):
    dynamodb_client = init_boto3_client("dynamodb")
    if dynamodb_client is False:
        raise Exception("MediaConvert client creation failed")
    try:
        uuid_string = str(uuid.uuid4())
        # TODO
        #   Handle existing uuid
        #  dynamo_search_response = dynamodb_client.query(
        #     TableName=environ['DYNAMODB_TABLE_NAME'],
        #     Key={
        #       "uuid":{
        #          "S":uuid
        #        }
        #     },
        #     AttributesToGet=['uuid'],
        #     ConsistentRead=True,
        # )
        dynamo_response = dynamodb_client.put_item(
            TableName=environ['DYNAMODB_TABLE_NAME'],
            Item={
                "uuid":{
                    "S":uuid_string
                },
                "video_name": {
                    "S":video_name
                },
                "mediaconvert_job_id": {
                    "S":job_id
                },
                "mediaconvert_job_status": {
                    "S":"STARTED"
                },
                "sample_rate":{
                    "N":sample_rate
                },
                "video_analysis_list": {
                    "SS":video_analysis_list
                }
            }
        )
    except Exception as e:
        print("Exception while writing item to DynamoDB \n",e)
        return False

    return True


def init_boto3_client(client_type="s3"):
    try:
        custom_client = client(client_type, region_name=region)
    except Exception as e:
        print("An error occurred while initializing "+client_type.capitalize()+"Client \n", e)
        return False

    return custom_client