# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not
# use this file except in compliance with the License. A copy of the
# License is located at:
#    http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, expressi
# or implied. See the License for the specific language governing permissions
# and limitations under the License.

from os import environ
from json import dumps, loads
from boto3 import resource
from boto3.dynamodb.conditions import Key
from concurrent.futures import ThreadPoolExecutor, as_completed

TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])
ANALYSIS_LIST = environ['ANALYSIS_LIST']

RESPONSE_PATTERN = {
    'statusCode': 200,
    'isBase64Encoded': False,
    'headers': {
        'Access-Control-Allow-Origin': '*'
    }
}


def lambda_handler(event, context):
    response = {'msg': '', 'data': {}}
    print('Processing event:\n' + dumps(event))
    print(ANALYSIS_LIST)
    print('---')
    event['body'] = loads(event['body'])
    print('Request Body: \n', event['body'])

    query_spec = validate_request(event['body'])
    if query_spec is False:
        RESPONSE_PATTERN['statusCode'] = 400
        response['msg'] = 'Wrong or missing parameters, verify your request'
        RESPONSE_PATTERN['body'] = dumps(response)
        return (RESPONSE_PATTERN)

    record = query_item(query_spec)

    if record is False:
        RESPONSE_PATTERN['statusCode'] = 404
        response[
            'msg'
        ] = 'No video analysis found with specified query attributes, please verify you have the correct S3Key and SampleRate/JobId'
        RESPONSE_PATTERN['body'] = dumps(response)
        return (RESPONSE_PATTERN)

    analysis, query_results = get_analysis_dynamo_results(record, query_spec)
    record['AnalysisPerformed'] = analysis['analysis']
    #print(query_results)

    msg = ""
    for index, value in record.items():
        msg += " " + str(index) + ": " + str(value)

    response['msg'] = "Query response for item " + msg
    response['data'] = query_results
    response['data']['dynamo_record'] = record

    #print(response)

    RESPONSE_PATTERN['body'] = dumps(response)

    return (RESPONSE_PATTERN)


def get_analysis_dynamo_results(item, query):

    print("Getting results for \n", item)
    all_results = {}

    analysis_list = TABLE.query(
        KeyConditionExpression=Key('S3Key').eq(item['S3Key']) &
        Key('AttrType').eq('frm/' + str(item['SampleRate']))
    )['Items'][0]

    if query['Analysis'] == 'all':
        parsed_list = ANALYSIS_LIST
        parsed_list = parsed_list.replace("'", '')
        parsed_list = parsed_list.replace("[", '')
        parsed_list = parsed_list.replace("]", '')
        parsed_list = parsed_list.split(',')
        with ThreadPoolExecutor(max_workers=len(ANALYSIS_LIST)) as pool:
            futures = [
                pool.submit(
                    get_results_by_analysis, item['S3Key'],
                    "ana/" + analysis + "/" + item['SampleRate'] + "/", analysis
                ) for analysis in parsed_list
            ]
            for r in as_completed(futures):
                analysis, data = r.result()
                if data is not False:
                    all_results[analysis] = data
    else:
        analysis_base_name = "ana/" + query['Analysis'] + "/" + item[
            'SampleRate'] + "/"
        analysis, results = get_results_by_analysis(
            item['S3Key'], analysis_base_name, query['Analysis']
        )
        if results is not False:
            all_results[analysis] = results

    return analysis_list, all_results


def validate_request(body):
    if 'S3Key' not in body:
        print("Missing required parameter S3Key on body")
        return False

    by_job_id = True if 'JobId' in body else False
    by_sample_rate = True if 'SampleRate' in body else False
    if by_job_id is False and by_sample_rate is False:
        print(
            "Missing required query parameters either JobId or SampleRate on request"
        )
        return False

    query_structure = {'S3Key': body['S3Key']}
    if by_job_id:
        query_structure['query_by'] = 'JobId'
        query_structure['JobId'] = body['JobId']
    if by_sample_rate:
        query_structure['query_by'] = 'SampleRate'
        query_structure['SampleRate'] = body['SampleRate']

    if 'Analysis' in body:
        if body['Analysis'] != 'all' and body['Analysis'] not in ANALYSIS_LIST:
            print(
                "Analysis must be either 'all' or one from the list ",
                ANALYSIS_LIST
            )
            return False
        else:
            query_structure['Analysis'] = body['Analysis']
    else:
        query_structure['Analysis'] = 'all'

    return query_structure


def query_item(query):
    if query['query_by'] == 'JobId':
        dynamo_record = TABLE.query(
            IndexName='JobIdIndex',
            KeyConditionExpression=Key('S3Key').eq(query['S3Key']) &
            Key('JobId').eq(query['JobId'])
        )['Items']
    elif query['query_by'] == 'SampleRate':
        dynamo_record = TABLE.query(
            KeyConditionExpression=Key('S3Key').eq(query['S3Key']) &
            Key('AttrType').eq('frm/' + str(query['SampleRate']))
        )['Items']
    else:
        print("Unsupported query by")
        return False

    if dynamo_record == []:
        return False
    else:
        return get_item_info(dynamo_record[0])


def get_item_info(dynamo_record):
    item = {
        'S3Key': dynamo_record['S3Key'],
        'JobId': dynamo_record['JobId'],
        'SampleRate': get_samplerate_from_attrtype(dynamo_record['AttrType'])
    }
    return item


def get_samplerate_from_attrtype(attr_type):
    segments = attr_type.split('/')
    if len(segments) <= 3:
        return segments[-1]
    elif len(segments) == 4:
        return segments[2]
    else:
        return False


def get_results_by_analysis(s3_key, analysis_base_name, analysis):
    print("querying results for " + s3_key + " & " + analysis_base_name)
    results = TABLE.query(
        KeyConditionExpression=Key('S3Key').eq(s3_key) &
        Key('AttrType').begins_with(analysis_base_name)
    )['Items']

    if results == []:
        return analysis, False

    all_results = []
    i = 0
    while i < 10:
        for result in results:
            if result not in all_results:
                all_results.append(result)

        if i < 9:
            results = TABLE.query(
                KeyConditionExpression=Key('S3Key').eq(s3_key) &
                Key('AttrType').between(
                    analysis_base_name + str(i), analysis_base_name +
                    str(i + 1)
                )
            )['Items']
        else:
            results = TABLE.query(
                KeyConditionExpression=Key('S3Key').eq(s3_key) &
                Key('AttrType').begins_with(analysis_base_name + str(i))
            )['Items']
        i += 1
    return analysis, all_results
