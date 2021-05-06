from boto3 import resource

class ResultSaver:
    def __init__(self, table):
        self.ddb_table = resource('dynamodb').Table(table)
        # TODO: Build a common saver for all analysis