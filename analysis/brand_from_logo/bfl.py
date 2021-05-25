from os import environ
from boto3 import client, resource
from json import load, dumps, loads
from time import sleep

REKOGNITION = client('rekognition')
SNS = client('sns')
TABLE = resource('dynamodb').Table(environ['DDB_TABLE'])

def lambda_handler(event, context):
    message = loads(
        event['Records'][0]['Sns']['Message']
    )
    print('Starting text extraction ..')

    # Group text detections by timestamp
    with TABLE.batch_writer() as batch:
        return batch