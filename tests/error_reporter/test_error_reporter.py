from unittest import TestCase
from libraries.tools.error_reporter import ErrorReporter
from mock import patch

@patch('libraries.tools.error_reporter.DynamoDBHandler.get_item')
@patch('libraries.tools.error_reporter.DynamoDBHandler.update_item')
@patch('libraries.tools.error_reporter.DynamoDBHandler.delete_item')
class TestHandler(TestCase):

    def make_reporter(self):
        return ErrorReporter(reporter='my-lambda',
                              table='db-table',
                              request_id='my-request-id',
                              to_email='recipient@example.com',
                              from_email='sender@example.com')


    def test_add_first_error(self, mock_delete, mock_update, mock_get):
        """
        If there is no report start a new one
        :param mock_delete:
        :param mock_update:
        :param mock_get:
        :return:
        """
        mock_get.return_value = None
        reporter = self.make_reporter()
        self.assertIsNone(reporter._report)

        reporter.add_error('error message')

        mock_get.assert_called_once_with({'lambda':'my-lambda'})
        mock_update.assert_not_called()
        mock_delete.assert_not_called()
        self.assertEqual(1, len(reporter._report['errors']))

    def test_add_second_error(self, mock_delete, mock_update, mock_get):
        """
        If the reporter is not new then append errors
        :param mock_delete:
        :param mock_update:
        :param mock_get:
        :return:
        """
        mock_get.return_value = {
            'errors': ['first error'],
            'reporters': ['my-request-id']
        }
        reporter = self.make_reporter()
        self.assertIsNone(reporter._report)

        reporter.add_error('second second')

        mock_get.assert_called_once_with({'lambda':'my-lambda'})
        mock_update.assert_not_called()
        mock_delete.assert_not_called()
        self.assertEqual(2, len(reporter._report['errors']))

    def test_restart_report(self, mock_delete, mock_update, mock_get):
        """
        if the reporter is new then restart
        :param mock_delete:
        :param mock_update:
        :param mock_get:
        :return:
        """
        mock_get.return_value = {
            'errors': ['old error'],
            'reporters': ['my-old-request-id']
        }
        reporter = self.make_reporter()
        self.assertIsNone(reporter._report)

        reporter.add_error('new error')

        mock_get.assert_called_once_with({'lambda':'my-lambda'})
        mock_update.assert_not_called()
        mock_delete.assert_not_called()
        self.assertEqual(1, len(reporter._report['errors']))
        self.assertEqual('new error', reporter._report['errors'][0]['message'])

    def test_commit_without_errors(self, mock_delete, mock_update, mock_get):
        reporter = self.make_reporter()
        self.assertIsNone(reporter._report)

        reporter.commit()

        mock_delete.assert_called_once_with({'lambda': 'my-lambda'})
        mock_update.assert_not_called()
        mock_get.assert_not_called()

    def test_commit_with_error(self, mock_delete, mock_update, mock_get):
        reporter = self.make_reporter()
        self.assertIsNone(reporter._report)

        reporter._report = {
            'lambda': 'my-lambda',
            'reporters': ['my-request-id'],
            'errors': [{
                'message': 'my error',
                'timestamp': '2017-08-15'
            }]
        }
        reporter.commit()

        mock_delete.assert_not_called()
        mock_update.assert_called_once_with({'lambda': 'my-lambda'}, {
            'reporters': ['my-request-id'],
            'errors': [{'message': 'my error', 'timestamp':'2017-08-15'}],
            'lambda': 'my-lambda'
        })
        mock_get.assert_not_called()

    @patch('libraries.tools.error_reporter.SESHandler.send_email')
    def test_commit_request_limit(self, mock_send, mock_delete, mock_update, mock_get):
        reporter = self.make_reporter()
        self.assertIsNone(reporter._report)

        reporter._report = {
            'lambda': 'my-lambda',
            'reporters': ['a-request-id', 'another-reporter', 'first-reporter', 'some-reporter'],
            'errors': [{
                'message': 'my error',
                'timestamp': '2017-08-15'
            }]
        }
        reporter.commit()

        mock_send.assert_called_once()
        mock_delete.assert_called_once_with({'lambda': 'my-lambda'})
        mock_update.assert_not_called()
        mock_get.assert_not_called()