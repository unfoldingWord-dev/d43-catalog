import os
import shutil
import tempfile
from unittest import TestCase

from libraries.tools.build_utils import get_build_rules

from libraries.tools.lambda_utils import wipe_temp


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
