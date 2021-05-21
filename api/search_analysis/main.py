from os import environ, terminal_size
import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from json import dumps

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

def create_queries(filters, action):
    return [
                {
                    "nested": {
                        "path": filters[0],
                        "query": {
                            "bool": {
                                action: list([
                                    create_filter(field_type, filters[0])
                                ] for field_type in filter_type.items())
                            }
                        }
                    }
                }
                for filter_type in filters[1] 
            ]

def create_filter(field_type, filter_type):
    if field_type[0]=='accuracy':
        return {"range": {"{}.accuracy".format(filter_type): {"gte": field_type[1]}}}
    else:
        return {"match": {"{}.{}".format(filter_type, field_type[0]): field_type[1]}}

def search_documents(filters):
    transformed = {
        "query": {
            "bool": {
                "must": []
            }
        },
        "aggs": {
            "by_id": {
                "terms": {
                    "field": "S3_Key.keyword"
                },
                "aggs" : {
                    "same_ids": {
                        "top_hits": {
                            "size":10
                        }
                    }
                }
            }
        }
    }
    if 'must' in filters.keys():
        for filter_type in filters['must'].items():
            transformed['query']['bool']['must'].append(
                create_queries(filter_type, 'must')) 
    if 'avoid' in filters.keys():
        for filter_type in filters['must'].items():
            transformed['query']['bool']['must'].append(
                create_queries(filter_type, 'must_not')
            )
    if 'S3_Key' in filters.keys():
        transformed['query']['bool']['must'].append(
            {"match": {"S3_Key.keyword": filters['S3_Key']}}
        )
    if 'FrameRate' in filters.keys():
        transformed['query']['bool']['must'].append(
            {"match": {"FrameRate": filters['FrameRate']}}
        )
    print(transformed)
    search = ES_CLIENT.search(
        index='analysis',
        body=transformed
        # filter_path=['hits.hits._id', 'hits.hits._type']
    )
    return search
def lambda_handler(event, context):
    search_results = search_documents(event)
    print(search_results)
    if search_results['hits']['total'] == 0:
        return 'No results found!'
    else:
        return search_results['hits']