from __future__ import print_function
import boto3
from json import dumps
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from os import environ
from IndexDefinition import IndexDefinition
from hashlib import md5

INDEX_NAME = 'analysis-results'


def connect_es(esEndPoint):
    __credentials = boto3.Session().get_credentials()
    __awsauth = AWS4Auth(
        __credentials.access_key,
        __credentials.secret_key,
        'us-east-1',
        'es',
        session_token=__credentials.token
    )
    print('Connecting to the ES Endpoint {0}'.format(esEndPoint))
    try:
        esClient = Elasticsearch(
            hosts=[{
                'host': esEndPoint,
                'port': 443
            }],
            http_auth=__awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        return esClient
    except Exception as E:
        print("Unable to connect to {0}".format(esEndPoint))
        print(E)
        exit(3)


def create_index(esClient, indexDoc):
    try:
        res = esClient.indices.exists(INDEX_NAME)
        if res is False:
            esClient.indices.create(INDEX_NAME, body=indexDoc)
        return 1
    except Exception as E:
        print("Unable to Create Index {0}".format(INDEX_NAME))
        print(E)
        exit(4)


def index_video_record(esClient, key, document):
    routing = int(md5(bytes(key, 'utf-8')).hexdigest(), 16) % 5
    exists = esClient.exists(index=INDEX_NAME, id=key, routing=routing)
    if not exists:
        try:
            esClient.create(
                index=INDEX_NAME, id=key, body=document, routing=routing
            )
        except Exception as E:
            print("Video not indexed")
            print("Error: ", E)
            exit(5)
    return routing


def index_frame_record(esClient, key, document, routing):
    print(document)
    if not esClient.exists(index=INDEX_NAME, id=key, routing=routing):
        try:
            esClient.create(
                index=INDEX_NAME, id=key, body=document, routing=routing
            )
        except Exception as E:
            print("frame not indexed")
            print("Error: ", E)
            exit(5)
    else:
        try:
            esClient.update(
                index=INDEX_NAME,
                id=key,
                body={"doc": document},
                doc_type='_doc',
                routing=routing
            )
        except Exception as E:
            print("frame not indexed")
            print("Error: ", E)
            exit(5)


def gen_video_record(anaysisResult):
    return {
        "S3_Key": anaysisResult['S3_Key'],
        "SampleRate": anaysisResult['SampleRate'],
        "JobId": anaysisResult['JobId'],
        "doc_type": "video"
    }


def gen_documents(analysisResult, parentId):
    for timestamp in analysisResult['results'].items():
        yield {
            'S3_Key': analysisResult['S3_Key'].replace('/', '-'),
            'Timestamp': int(timestamp[0]),
            analysisResult['type']: timestamp[1],
            'doc_type': {
                'name': 'frame',
                'parent': parentId
            }
        }


""" 
---------------
Indexing Lambda
---------------
Indexing steps:
    # 1. Create index if not exists
    # 2. Index video document if not exists
    # 3. Index individual frames if not exists
        # 3.1. Update property if frame exists
"""

ES_CLIENT = connect_es(environ['DOMAIN_ENDPOINT'])


def lambda_handler(event, context):
    print("Received event: " + dumps(event, indent=2))
    responses = []
    if create_index(ES_CLIENT, IndexDefinition):
        try:
            video_key = '{}-{}'.format(event['S3_Key'], event['SampleRate'])
            routing = index_video_record(
                ES_CLIENT, video_key, gen_video_record(event)
            )
            for document in gen_documents(event, video_key):
                print(document)
                responses.append(
                    index_frame_record(
                        ES_CLIENT, '{}-{}'.format(
                            document['S3_Key'], document['Timestamp']
                        ), document, routing
                    )
                )
            return responses
        except Exception as e:
            print('Failed to Index: {}'.format(e))
            raise e
    else:
        print("Failed to create index")
