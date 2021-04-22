from BaseHelper import BaseHelper

class DynamoDBHelper(BaseHelper):

    def __init__(self,table_name,region):
        super().__init__("DynamoDB")
        self.table_name = table_name
        self.region = region
        self.client = self.init_boto3_client("dynamodb",self.region)

    def write_to_dynamodb(self,item):
        try:
            dynamo_response = self.client.put_item(
                TableName=self.table_name,
                Item=item
            )
        except Exception as e:
            print("Exception while writing item to DynamoDB \n", e)
            return False
        else:
            return dynamo_response

    def update_dynamodb_item(self,primary_key_set,update_expression,expression_attributes_values):
        try:
            dynamo_response = self.client.update_item(
                TableName=self.table_name,
                Key=primary_key_set,
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attributes_values,
                ReturnValues="ALL_NEW"
            )
        except Exception as e:
            print("Exception while writing item to DynamoDB \n",e)
            return False

        return dynamo_response['Attributes']

    def query_item(self,index_name,condition_expression,condition_attributes,items = "FIRST"):
        try:
            dynamo_search_response = self.client.query(
                TableName=self.table_name,
                IndexName=index_name,
                Select='ALL_ATTRIBUTES',
                KeyConditionExpression=condition_expression,
                ExpressionAttributeValues=condition_attributes
            )
        except Exception as e:
            print("Exception while getting item from DynamoDB \n",e)
            return False
        else:
            if(len(dynamo_search_response['Items']) <= 0):
                return False
        if items == "FIRST":
            return dynamo_search_response['Items'][0]
        else:
            return dynamo_search_response['Items']

    def get_item(self,primary_key,projection_expression_attributes="",expression_attribute_names = {},consistent_read = True):
        try:
            if projection_expression_attributes == "":
                dynamo_search_response = self.client.get_item(
                    TableName=self.table_name,
                    Key=primary_key,
                    ConsistentRead=consistent_read
                )
            else:
                if(expression_attribute_names is not {}):
                    dynamo_search_response = self.client.get_item(
                        TableName=self.table_name,
                        Key = primary_key,
                        ConsistentRead=consistent_read,
                        ProjectionExpression=projection_expression_attributes
                    )
                else:
                    dynamo_search_response = self.client.get_item(
                        TableName=self.table_name,
                        Key = primary_key,
                        ConsistentRead=consistent_read,
                        ExpressionAttributeNames=expression_attribute_names,
                        ProjectionExpression=projection_expression_attributes
                    )

        except Exception as e:
            print("Exception while getting item from DynamoDB \n",e)
            return False
        else:
            if('Item' not in dynamo_search_response):
                return False
            if (dynamo_search_response['Item'] is {}):
                return False
        return dynamo_search_response['Item']

    def build_update_expression(self,attribute, value, value_type, previous_expression="", previous_values={}):
        if previous_expression != "":
            if "SET" in previous_expression:
                previous_expression = previous_expression + ", " + attribute + " = :" + attribute + "val"
            else:
                previous_expression = "SET " + previous_expression + ", " + attribute + " = :" + attribute + "val"
        else:
            previous_expression = "SET " + attribute + " = :" + attribute + "val"

        if len(previous_values) <= 0 or previous_values is {}:
            previous_values = {
                ":" + attribute + "val": {
                    value_type: value
                }
            }
        else:
            previous_values[":" + attribute + "val"] = {
                value_type: value
            }

        return previous_expression, previous_values

    def build_item_attribute_structure(self,key_name,key_type,value,item = {}):
        item[key_name] = {key_type,value}
        return item