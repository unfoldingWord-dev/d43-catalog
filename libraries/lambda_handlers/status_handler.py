import arrow

from d43_aws_tools import DynamoDBHandler
from libraries.lambda_handlers.handler import Handler

class StatusHandler(Handler):

    def _run(self):
        self.status_db = DynamoDBHandler('{}d43-catalog-status'.format(self.stage_prefix()))
        self.errors_db = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix()))

        response = {
            'functions': []
        }
        api_status = self.status_db.query_items()
        api_error = self.errors_db.query_items()

        errors = {}
        for error in api_error:
            errors[error['lambda']] = error['errors']

        # load catalog status
        for api in api_status:
            status = self.make_function_status(api['api_version'], errors)
            # catalogs have their own status and timestamp
            status['status'] = api['state']
            status['timestamp'] = api['timestamp']
            response['functions'].append(status)

        # load remaining lambda status
        response['functions'].append(self.make_function_status('webhook', errors))
        response['functions'].append(self.make_function_status('signing', errors))
        response['functions'].append(self.make_function_status('acceptance', errors))
        response['functions'].append(self.make_function_status('fork', errors))
        response['functions'].append(self.make_function_status('trigger', errors))

        return response

    def make_function_status(self, name, errors):
        status = {
            'name': name,
            'status': 'complete',
            'lambda': self.get_full_lambda_name(name),
            'timestamp': arrow.utcnow().isoformat(),
            'errors': []
        }
        if status['lambda'] in errors:
            status['errors'] = errors[status['lambda']]
        return status

    def get_full_lambda_name(self, name):
        """
        Returns the full name of a lambda.
        :param name: the short name of the lambda. Or you can pass in the short name of an api catalog.
        :return:
        """
        lambda_prefix = 'd43-catalog_'
        if name == '3':
            return '{}{}catalog'.format(self.stage_prefix(), lambda_prefix)
        elif name == 'ts.2':
            return '{}{}ts_v2_catalog'.format(self.stage_prefix(), lambda_prefix)
        elif name == 'uw.2':
            return '{}{}uw_v2_catalog'.format(self.stage_prefix(), lambda_prefix)
        else:
            return '{}{}{}'.format(self.stage_prefix(), lambda_prefix, name)