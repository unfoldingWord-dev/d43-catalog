import os
import shutil
import tempfile
import unittest
from libraries.tools.test_utils import is_travis, Bunch
from unittest import TestCase

from libraries.tools.build_utils import get_build_rules
from libraries.tools.mocks import MockDynamodbHandler
from libraries.tools.lambda_utils import wipe_temp, is_lambda_running, set_lambda_running, clear_lambda_running, lambda_min_remaining


class TestTools(TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='test_tools_')

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_tools(self):
        self.assertEqual([], get_build_rules({}))
        self.assertEqual([], get_build_rules({'somekey': 'somevalue'}))
        self.assertEqual([], get_build_rules([]))
        self.assertEqual([], get_build_rules(None))
        self.assertEqual([], get_build_rules({'build_rules':[]}))

        obj = {'build_rules':['some_rule', 'test.test_rule', 'default.default_rule']}
        self.assertEqual(obj['build_rules'], get_build_rules(obj))
        self.assertEqual(['test_rule'], get_build_rules(obj, 'test'))
        self.assertEqual(['default_rule'], get_build_rules(obj, 'default'))

    def test_wipe_temp_empty(self):
        files_before = [name for name in os.listdir(self.temp_dir) if os.path.isfile(name)]
        self.assertEqual(0, len(files_before))

        wipe_temp(tmp_dir=self.temp_dir)

        files_after = [name for name in os.listdir(self.temp_dir) if os.path.isfile(name)]
        self.assertTrue(os.path.exists(self.temp_dir))
        self.assertEqual(0, len(files_after))

    def test_wipe_temp_full(self):
        files_before = [name for name in os.listdir(self.temp_dir) if os.path.isfile(name)]
        self.assertEqual(0, len(files_before))

        wipe_temp(tmp_dir=self.temp_dir)

        files_after = [name for name in os.listdir(self.temp_dir) if os.path.isfile(name)]
        self.assertTrue(os.path.exists(self.temp_dir))
        self.assertEqual(0, len(files_after))

    @unittest.skipIf(is_travis(), 'Skipping test_is_lambda_not_running on travis')
    def test_is_lambda_is_not_running(self):
        dbname = 'dev-d43-catalog-running'
        context = Bunch(function_name='test', aws_request_id='test', get_remaining_time_in_millis=lambda: 300000)
        mockDB = MockDynamodbHandler()

        clear_lambda_running(context=context,
                             dbname=dbname,
                             dynamodb_handler=lambda name:mockDB)
        result = is_lambda_running(context, dbname)
        self.assertFalse(result)

    @unittest.skipIf(is_travis(), 'Skipping test_is_lambda_running on travis')
    def test_is_lambda_is_running(self):
        dbname = 'dev-d43-catalog-running'
        context = Bunch(function_name='test', aws_request_id='test', get_remaining_time_in_millis=lambda: 300000)
        mockDB = MockDynamodbHandler()

        set_lambda_running(context=context,
                           dbname=dbname,
                           dynamodb_handler=lambda name:mockDB)
        result = is_lambda_running(context=context,
                                   dbname=dbname,
                                   dynamodb_handler=lambda name:mockDB)
        self.assertTrue(result)

    @unittest.skipIf(is_travis(), 'Skipping test_lambda_is_running_with_suffix on travis')
    def test_lambda_is_running_with_suffix(self):
        dbname = 'dev-d43-catalog-running'
        context = Bunch(function_name='test', aws_request_id='test', get_remaining_time_in_millis=lambda: 300000)
        mockDB = MockDynamodbHandler()

        set_lambda_running(context=context,
                           dbname=dbname,
                           lambda_suffix='fun',
                           dynamodb_handler=lambda name: mockDB)
        result = is_lambda_running(context=context,
                                   dbname=dbname,
                                   lambda_suffix='fun',
                                   dynamodb_handler=lambda name: mockDB)
        self.assertTrue(result)
        self.assertEqual('test.fun', mockDB._last_inserted_item['lambda'])

    @unittest.skipIf(is_travis(), 'Skipping test_lambda_min_remaining on travis')
    def test_lambda_min_remaining(self):
        context = Bunch(get_remaining_time_in_millis=lambda: 300000)

        minutes = lambda_min_remaining(context)
        self.assertEqual(5, minutes)
