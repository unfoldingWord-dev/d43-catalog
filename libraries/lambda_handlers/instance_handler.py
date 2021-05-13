# coding=utf-8

from __future__ import unicode_literals, print_function
from abc import ABCMeta
from libraries.lambda_handlers.handler import Handler
from libraries.tools.lambda_utils import set_lambda_running, lambda_sec_remaining


class InstanceHandler(Handler):
    """
    Extends the base lambda handler to only allow a single instance
    of the handler to run at any given time.
    """
    __metaclass__ = ABCMeta

    def run(self, **kwargs):
        # check if already running
        running_db_name = '{}d43-catalog-running'.format(self.stage_prefix())
        sec_remaining = lambda_sec_remaining(self.context, running_db_name)
        if sec_remaining > 0:
            self.logger.warning('Lambda started before last execution timed out ({}min remaining). Aborting.'.format(round(sec_remaining / 60)))
            return False
        else:
            set_lambda_running(self.context, running_db_name)

        # continue normal execution
        return super(InstanceHandler, self).run(**kwargs)
