from __future__ import print_function
from pprint import pprint
import boto3
import json
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, 'us-east-1', service, session_token=credentials.token)

def connectES(esEndPoint):
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

def createIndex(esClient, indexDoc):
    try:
        res = esClient.indices.exists('metadata-store')
        if res is False:
            esClient.indices.create('metadata-store', body=indexDoc)
        return 1
    except Exception as E:
            print("Unable to Create Index {0}".format("metadata-store"))
            print(E)
            exit(4)

def indexDocElement(esClient,key,document):
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

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    esClient = connectES("search-my-domain-yrvyusealrb5eot5icbg6lffwy.us-east-1.es.amazonaws.com")
    index = {
      "doc": {},
      "upsert": {}
    }
    index['doc'] = index['upsert'] = event['document']

    # createIndex(esClient) # In case we need to create an index

    try:
        response = indexDocElement(
            esClient,
            event['document']['S3_Key'].replace('/','-'),
            index)
        return response
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e

