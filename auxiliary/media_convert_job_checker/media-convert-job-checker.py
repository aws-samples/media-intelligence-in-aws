# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from os import environ
from boto3 import client, resource
from boto3.dynamodb.conditions import Key
from json import dumps

mediaconvert = client('mediaconvert')
endpoint = mediaconvert.describe_endpoints(MaxResults=1, Mode='DEFAULT'
                                          )['Endpoints'][0]['Url']
mediaconvert = client('mediaconvert', endpoint_url=endpoint)
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
SNS_TOPIC = resource('sns').Topic(environ['SNS_TOPIC'])


def lambda_handler(event, context):
    print("Processing event \n", dumps(event))

    JobId = event['Records'][0]['Sns']['Message']
    JobId = JobId.replace("job_id:", "")
    JobId = sanitize_string(JobId)

    mc_job = check_mediaconvert_job(JobId)
    if mc_job is False:
        print("Failed getting job id " + JobId)
        raise Exception("No MediaConvert job found with id: " + JobId)

    mc_job = mc_job['Job']

    s3_key = mc_job['Settings']['Inputs'][0]['FileInput'].replace(
        's3://{}/'.format(environ['IN_S3_BUCKET']), ''
    )

    Item = TABLE.query(
        IndexName='JobIdIndex',
        KeyConditionExpression=Key('S3Key').eq(s3_key) & Key('JobId').eq(JobId),
        Select='ALL_ATTRIBUTES'
    )['Items'][0]

    if Item is False or Item == []:
        raise Exception(
            "No item found on DynamoDB with: " + s3_key + " & " + JobId
        )

    sample_rate = int(Item['AttrType'].replace('frm/', ''))
    new_item = {
        'S3Key': s3_key,
        'AttrType': Item['AttrType'],
        'JobId': JobId,
        'SampleRate': sample_rate,
        'analysis': Item['analysis']
    }
    if mc_job['Status'] == 'CANCELED' or mc_job['Status'] == 'ERROR':
        print("MediaConvert Job failed, aborting workflow")
        new_item['Status'] = 'FAILED'
        TABLE.put_item(Item=new_item)
        SNS_EMAIL_TOPIC = resource('sns').Topic(environ['SNS_EMAIL_TOPIC'])
        return SNS_EMAIL_TOPIC.publish(
            Message=" MediaConvert Job Failed for S3Key: " + s3_key +
            " and JobId: " + JobId +
            " please refer to the Elemental MediaConvert console \n " +
            " \n\n Job details: https://" + environ['AWS_REGION'] +
            ".console.aws.amazon.com/mediaconvert/home?region=" +
            environ['AWS_REGION'] + "#/jobs/summary/" + JobId
        )
    else:
        new_item['Status'] = 'MediaConvert COMPLETED'
        TABLE.put_item(Item=new_item)
        return SNS_TOPIC.publish(
            Message=dumps(
                {
                    "S3Key":
                        Item['S3Key'],
                    "SampleRate":
                        sample_rate,
                    "JobId":
                        JobId,
                    "OutputPath":
                        mc_job['Settings']['OutputGroups'][0]
                        ['OutputGroupSettings']['FileGroupSettings']
                        ['Destination']
                }
            ),
            MessageAttributes={
                'analysis':
                    {
                        'DataType': 'String.Array',
                        'StringValue': dumps(Item['analysis'])
                    }
            }
        )


def check_mediaconvert_job(job_id):

    if mediaconvert is False:
        raise Exception("MediaConvert client creation failed")

    try:
        job_response = mediaconvert.get_job(Id=job_id)
    except Exception as e:
        print("MediaConvert get job exception \n", e)
        return False

    return job_response


def sanitize_string(string_variable):
    string_variable = string_variable.replace("\n", "")
    string_variable = string_variable.replace("\"", "")
    string_variable = string_variable.replace("\'", "")
    string_variable = string_variable.replace("\r", "")
    string_variable = string_variable.replace(":", "")
    return string_variable
