# coding=utf-8
from __future__ import unicode_literals
import os
import shutil
import tempfile
from unittest import TestCase
from mock import patch
from libraries.tools.ts_v2_utils import build_usx, build_json_source_from_usx, tn_tsv_to_json


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

    def test_tn_tsv_to_json(self, mock_reporter):
        chunks = {
            '01': ['01', '03', '05'],
            '02': ['01', '04', '07'],
        }
        tsv = [
            {'Chapter': 'front', 'Verse': 'intro'},
            {'Chapter': '1', 'Verse': '1', 'GLQuote': 'in', 'OccurrenceNote': 'in notes'},
            {'Chapter': '1', 'Verse': '2', 'GLQuote': 'the', 'OccurrenceNote': 'the notes'},
            {'Chapter': '1', 'Verse': '3', 'GLQuote': 'beginning', 'OccurrenceNote': 'beginning notes'},
            {'Chapter': '1', 'Verse': '4', 'GLQuote': 'God', 'OccurrenceNote': 'God notes'},
            {'Chapter': '2', 'Verse': '1', 'GLQuote': 'in', 'OccurrenceNote': 'in notes'},
            {'Chapter': '2', 'Verse': '2', 'GLQuote': 'the', 'OccurrenceNote': 'the notes'},
            {'Chapter': '2', 'Verse': '3', 'GLQuote': 'beginning', 'OccurrenceNote': 'beginning notes'},
            {'Chapter': '2', 'Verse': '4', 'GLQuote': 'God', 'OccurrenceNote': 'God notes'},
            {'Chapter': '2', 'Verse': '5', 'GLQuote': 'created', 'OccurrenceNote': 'created notes'},
        ]
        expected = [
            {
                'id': '01-01',
                'tn': [
                    {'ref': 'in', 'text': 'in notes'},
                    {'ref': 'the', 'text': 'the notes'}
                ]
            },
            {
                'id': '01-03',
                'tn': [
                    {'ref': 'beginning', 'text': 'beginning notes'},
                    {'ref': 'God', 'text': 'God notes'}
                ]
            },
            {
                'id': '02-01',
                'tn': [
                    {'ref': 'in', 'text': 'in notes'},
                    {'ref': 'the', 'text': 'the notes'},
                    {'ref': 'beginning', 'text': 'beginning notes'}
                ]
            },
            {
                'id': '02-04',
                'tn': [
                    {'ref': 'God', 'text': 'God notes'},
                    {'ref': 'created', 'text': 'created notes'}
                ]
            }
        ]
        json = tn_tsv_to_json(tsv, chunks)
        self.assertEqual(expected, json)
        assert not mock_reporter.called
