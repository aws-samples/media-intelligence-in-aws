from boto3 import client

class BaseHelper:
    def __init__(self,name="MainHelper"):
        self.name = name

    def init_boto3_client(self,client_type="s3",region="us-central-1"):
        try:
            custom_client = client(client_type, region_name=region)
        except Exception as e:
            self.log_error("An error occurred while initializing " + client_type.capitalize() + "Client \n",e)
            return False

        return custom_client

    def log_error(self,msg,e):
        print(self.name + "Helper Error:" + msg,e)

    def sanitize_string(self,string_variable):
        string_variable = string_variable.replace("\n", "")
        string_variable = string_variable.replace("\"", "")
        string_variable = string_variable.replace("\'", "")
        string_variable = string_variable.replace("\r", "")
        string_variable = string_variable.replace(":", "")
        return string_variable