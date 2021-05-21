from __future__ import print_function
from pprint import pprint
import boto3
import json
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from os import environ

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, 'us-east-1', 'es', session_token=credentials.token)

def connect_es(esEndPoint):
    print ('Connecting to the ES Endpoint {0}'.format(esEndPoint))
    try:
        esClient = Elasticsearch(
            hosts=[{'host': esEndPoint, 'port': 443}],
            http_auth = awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection)
        return esClient
    except Exception as E:
        print("Unable to connect to {0}".format(esEndPoint))
        print(E)
        exit(3)

ES_CLIENT = connect_es(environ['DOMAIN_ENDPOINT'])
# ES_CLIENT = connect_es("search-my-domain-yrvyusealrb5eot5icbg6lffwy.us-east-1.es.amazonaws.com")
def create_index(esClient, indexDoc):
    try:
        res = esClient.indices.exists('metadata-store')
        if res is False:
            esClient.indices.create('metadata-store', body=indexDoc)
        return 1
    except Exception as E:
            print("Unable to Create Index {0}".format("metadata-store"))
            print(E)
            exit(4)

def index_doc_element(esClient,key,document):
    # Performs an upsert on the index
    try:
        retval = esClient.update(
            id=key,
            index='analysis',
            doc_type='_doc',
            body=document
        )
        return retval
    except Exception as E:
        print("Document not indexed")
        print("Error: ",E)
        exit(5)	

def gen_documents(analysisResult):
    for timestamp in analysisResult['results'].items():
        yield {
            'S3_Key': analysisResult['S3_Key'].replace('/','-'),
            'timestamp': int(timestamp[0]),
            analysisResult['type']:timestamp[1],
            'JobId': analysisResult['JobId'],
            'FrameRate': analysisResult['FrameRate']
        }

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    index = {
      "doc": {},
      "upsert": {}
    }

    # createIndex(esClient) # In case we need to create an index

    try:
        for document in gen_documents(event):
            index['doc'] = index['upsert'] = document
            response = index_doc_element(
                ES_CLIENT,
                '{}-{}'.format(document["S3_Key"],document["timestamp"]),
                index
            )
        return response
    except Exception as e:
        print('Failed to Index: {}'.format(e))
        raise e
