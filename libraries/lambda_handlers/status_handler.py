from d43_aws_tools import DynamoDBHandler
from libraries.lambda_handlers.handler import Handler

class StatusHandler(Handler):
    def __init__(self, event, context):
        super(StatusHandler, self).__init__(event, context)

        self.status_db = DynamoDBHandler('{}d43-catalog-status'.format(self.stage_prefix()))
        self.errors_db = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix()))

    def _run(self):
        response = {
            'status': {},
            'timestamp': '',
            'errors': {}
        }
        api_status = self.status_db.query_items()
        for api in api_status:
            response['status'][api['api_version']] = {

            }
        return response;