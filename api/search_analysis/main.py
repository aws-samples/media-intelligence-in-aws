from os import environ
import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from json import dumps
from query  import small_query

INDEX_NAME = 'analysis-results'
RESPONSE_PATTERN = {
    'isBase64Encoded':False,
    'headers': {
    'Access-Control-Allow-Origin': '*'
    },
    'body':{}
}

def connect_es(esEndPoint):
    __credentials = boto3.Session().get_credentials()
    __awsauth = AWS4Auth(
        __credentials.access_key,
        __credentials.secret_key,
        'us-east-1',
        'es',
        session_token=__credentials.token
    )
    print ('Connecting to the ES Endpoint {0}'.format(esEndPoint))
    try:
        esClient = Elasticsearch(
            hosts=[{'host': esEndPoint, 'port': 443}],
            http_auth = __awsauth,
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
                                action: [
                                    create_filter(field_type, filters[0])
                                 for field_type in filter_type.items()]
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
    transformed = small_query

    if 'must' in filters.keys() or 'avoid' in filters.keys():
        transformed['query']['bool']['must'].append({
            'has_child': {
                'type':'frame',
                'query': {
                    'bool': {
                        'must': []
                    }
                },
                "inner_hits": {} # To retrieve frames
            }
        })
    if 'must' in filters.keys():
        transformed['query']['bool']['must'][0]['has_child']['query']['bool']['must'].append(
            {'bool':
                {'should': query for query in [create_queries(filter_type, 'must') for filter_type in filters['must'].items()]}
            })
    if 'avoid' in filters.keys():
        transformed['query']['bool']['must'][0]['has_child']['query']['bool']['must'].append(
            {'bool':
                {'must_not': query for query in [create_queries(filter_type, 'should') for filter_type in filters['avoid'].items()]}
            })
    if 'S3_Key' in filters.keys():
        transformed['query']['bool']['must'].append({
            "match": {
                "S3_Key": filters['S3_Key']
            }
        })
    if 'FrameRate' in filters.keys():
        transformed['query']['bool']['must'].append({
            "match": {
                "FrameRate": filters['FrameRate']
            }
        })
    try:
        search = ES_CLIENT.search(
            index=INDEX_NAME,
            body=transformed
        )
        return search
    except Exception as E:
        print("Failed to search")
        print("======== Query ========")
        print(dumps(transformed))
        print(E)
        exit(4)
def lambda_handler(event, context):
    search_results = search_documents(event)
    if search_results['hits']['total'] == 0:
        RESPONSE_PATTERN['body'] = 'No results found!'
        RESPONSE_PATTERN['statusCode'] = "400"
    else:
        RESPONSE_PATTERN['body'] = search_results['hits']['hits']
        RESPONSE_PATTERN['statusCode'] = "200"
    return RESPONSE_PATTERN