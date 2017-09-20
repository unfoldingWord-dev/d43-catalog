import arrow
import logging
import json

from d43_aws_tools import DynamoDBHandler, SESHandler

class ErrorReporter(object):

    def __init__(self, reporter, table, request_id, to_email, from_email, error_threshold=4):
        """

        :param reporter: the name of the lambda reporting the error
        :param table: the database table name
        :param request_id:  the AWS request id
        """
        self.__reporter = reporter
        self.__table_name = table
        self.__request_id = request_id
        self.__to_email = to_email
        self.__from_email = from_email
        self.__threshold = error_threshold
        self._report = None

        self.logger = logging.getLogger()  # type: logging._loggerClass

    def add_error(self, message):
        """
        Adds an error to the report
        :param string|list message:
        :return:
        """
        if isinstance(message, list):
            self.logger.info('Reporting Error: {}'.format(json.dumps(message)), exc_info=1)
        elif isinstance(message, str):
            self.logger.info('Reporting Error: {}'.format(message), exc_info=1)
        else:
            self.logger.warning('Unable to report error. Invalid type "{}"'.format(type(message)), exc_info=1)
            return

        db = DynamoDBHandler(self.__table_name)

        # load report
        if not self._report:
            item = db.get_item({'lambda': self.__reporter})
            if not item:
                item = {}
            self._report = {
                'errors': [],
                'lambda': self.__reporter,
                'reporters': []
            }
            self._report.update(item)

        # start new report
        if self.__request_id not in self._report['reporters']:
            self._report['errors'] = []
            self._report['reporters'].append(self.__request_id)

        # append errors to report
        if isinstance(message, list):
            timestamp = arrow.utcnow().isoformat()
            for m in message:
                self._report['errors'].append({
                    'message': m.decode('utf-8'),
                    'timestamp': timestamp
                })
        else:
            self._report['errors'].append({
                'message': message.decode('utf-8'),
                'timestamp': arrow.utcnow().isoformat()
            })

    def _record_report(self):
        """
        Stores the error report in the database
        :return:
        """
        if self._report:
            db = DynamoDBHandler(self.__table_name)
            db.update_item({'lambda': self.__reporter}, self._report)

    def _clear_report(self):
        """
        Removes the error report from the db
        :return:
        """
        db = DynamoDBHandler(self.__table_name)
        db.delete_item({'lambda': self.__reporter})
        self._report = None

    def commit(self):
        """
        Performs final operations after the reporter is finished being used.
        This includes saving the report and emailing administrators if necessary.
        :return:
        """
        if self._report and len(self._report['reporters']) >= self.__threshold:
            try:
                self._send_report()
                self._clear_report()
            except Exception as e:
                self.logger.error('Failed to report errors {}'.format(e.message), exc_info=1)
        elif not self._report or len(self._report['reporters']) == 0:
            # errors have been resolved
            self._clear_report()
        else:
            self._record_report()

    def _send_report(self):
        """
        Emails the error report to administrators
        :raises Exception: if the email could not be sent
        :return:
        """
        errors = []
        if self._report:
            errors = self._report['errors']

        text = ''
        html = ''
        for e in errors:
            text += '----------------\n{}\n{}'.format(e['timestamp'], e['message'])
            html += '<li><i>{}</i>: {}</li>'.format(e['timestamp'], e['message'])

        SESHandler().send_email(
            Source=self.__from_email,
            Destination={
                'ToAddresses': [
                    self.__to_email
                ]
            },
            Message={
                'Subject': {
                    'Data': 'ERRORS running {}'.format(self.__reporter),
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': 'Errors running {}\n\n{}'.format(self.__reporter, text),
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': 'Errors running {}\n\n<ul>{}</ul>'.format(self.__reporter, html)
                    }
                }
            }
        )