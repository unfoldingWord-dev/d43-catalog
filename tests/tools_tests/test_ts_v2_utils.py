# coding=utf-8
from __future__ import unicode_literals
import os
import shutil
import tempfile
from unittest import TestCase
from mock import patch
from libraries.tools.ts_v2_utils import build_usx, build_json_source_from_usx

@patch('libraries.lambda_handlers.handler.ErrorReporter')
class TestTsV2Utils(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='test_ts_v2_utils_')

    def tearDown(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_usx(self, mock_reporter):
        usfm_dir = os.path.join(self.resources_dir, 'usfm')
        usx_dir = os.path.join(self.temp_dir, 'usx')
        build_usx(usfm_dir, usx_dir)
        assert not mock_reporter.called

    def test_usx_to_json(self, mock_reporter):
        usx_file = os.path.join(self.resources_dir, 'PSA.usx')
        json = build_json_source_from_usx(usx_file, '2018', mock_reporter)
        assert not mock_reporter.called