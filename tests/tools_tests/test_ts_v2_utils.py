# coding=utf-8
from __future__ import unicode_literals
import os
import shutil
import tempfile
from unittest import TestCase
from mock import patch
from libraries.tools.file_utils import read_file
from libraries.tools.ts_v2_utils import build_usx, build_json_source_from_usx, usx_to_chunked_json, tn_tsv_to_json, index_tn_rc


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
        json = build_json_source_from_usx(usx_file, 'en', 'psa', '2018', mock_reporter)
        assert not mock_reporter.called

    def test_hebrew_usx_to_json(self, mock_reporter):
        usx_file = os.path.join(self.resources_dir, 'JOL.usx')
        json = build_json_source_from_usx(usx_file, 'hbo', 'jol', '2019', mock_reporter)
        assert not mock_reporter.called
        self.assertEquals(3, len(json['source']['chapters']))
        self.assertEquals('02-32', json['source']['chapters'][1]['frames'][17]['id'])
        self.assertEquals('03-01', json['source']['chapters'][2]['frames'][0]['id'])

    def test_usx_to_json_chunks_alt(self, mock_reporter):
        chunks = {
            '01': ['01', '03']
        }

        usx = [
            u'<para style="mt">PSALMS</para>\n',
            u'<para style="cl">Psalm</para>\n',
            u'<para style="ms">Book One</para>\n',
            u'<chapter number="1" style="c" />\n',
            u'<para style="q1">\n',
            u'<verse number="1" style="v" />Blessed is the man who does not walk in the advice of the wicked,</para>\n',
            u'<para style="q1">or stand in the pathway with sinners,</para>\n',
            u'<para style="q1">or sit in the assembly of mockers.</para>\n',
            u'<para style="q1">\n',
            u'<verse number="2" style="v" />But his delight is in the law of Yahweh,</para>\n',
            u'<para style="q1">and on his law he meditates day and night.\n',
            u'<para style="q1">\n',
            u'<verse number="3" style="v" />He will be like a tree planted by the streams of water</para>\n',
            u'<para style="q1">that produces its fruit in its season,</para>\n',
            u'<para style="q1">whose leaves do not wither;</para>\n',
            u'<para style="q1">whatever he does will prosper.\n',
            u'<para style="q1">\n',
            u'<verse number="4" style="v" />The wicked are not so,</para>\n',
            u'<para style="q1">but are instead like the chaff that the wind drives away.</para>\n',
        ]
        json = usx_to_chunked_json(usx, chunks, 'en', 'psa')
        self.assertEquals(json, [
            {
                'frames': [
                    {
                        'text': u'<para style="q1">\n<verse number="1" style="v" />Blessed is the man who does not walk in the advice of the wicked,</para>\n<para style="q1">or stand in the pathway with sinners,</para>\n<para style="q1">or sit in the assembly of mockers.</para>\n<para style="q1">\n<verse number="2" style="v" />But his delight is in the law of Yahweh,</para>\n<para style="q1">and on his law he meditates day and night.\n<para style="q1">',
                        'lastvs': u'2',
                        'id': '01-01',
                        'img': '',
                        'format': 'usx'
                     },
                    {
                        'text': u'<verse number="3" style="v" />He will be like a tree planted by the streams of water</para>\n<para style="q1">that produces its fruit in its season,</para>\n<para style="q1">whose leaves do not wither;</para>\n<para style="q1">whatever he does will prosper.\n<para style="q1">\n<verse number="4" style="v" />The wicked are not so,</para>\n<para style="q1">but are instead like the chaff that the wind drives away.</para>',
                        'lastvs': u'4',
                        'id': '01-03',
                        'img': '',
                        'format': 'usx'
                    }
                ],
                'ref': '',
                'number': '01',
                'title': ''
            }
        ])

    def test_usx_to_json_chunks(self, mock_reporter):
        chunks = {
            '01': ['01', '03', '04']
        }

        usx = [
            u'<para style="mt">PSALMS</para>\n',
            u'<para style="cl">Psalm</para>\n',
            u'<para style="ms">Book One</para>\n',
            u'<chapter number="1" style="c" />\n',
            u'<para style=\"cl\">Capítulo 1</para>\n\n',
            u'<para style="q1">\n',
            u'<verse number="1" style="v" />Blessed is the man who does not walk in the advice of the wicked,</para>\n',
            u'<para style="q1">or stand in the pathway with sinners,</para>\n',
            u'<para style="q1">or sit in the assembly of mockers.</para>\n',
            u'<para style="q1">\n',
            u'<verse number="2" style="v" />But his delight is in the law of Yahweh,</para>\n',
            u'<para style="q1">and on his law he meditates day and night.\n',
            u'<para style="q1">\n',
            u'<verse number="3" style="v" />He will be like a tree planted by the streams of water</para>\n',
            u'<para style="q1">that produces its fruit in its season,</para>\n',
            u'<para style="q1">whose leaves do not wither;</para>\n',
            u'<para style="q1">whatever he does will prosper.\n',
            u'<para style="q1">\n',
            u'<verse number="4" style="v" />The wicked are not so,</para>\n',
            u'<para style="q1">but are instead like the chaff that the wind drives away.</para>\n',
        ]
        json = usx_to_chunked_json(usx, chunks, 'en', 'psa')
        self.assertEquals(json, [
            {
                'frames': [
                    {
                        'text': u'<para style="q1">\n<verse number="1" style="v" />Blessed is the man who does not walk in the advice of the wicked,</para>\n<para style="q1">or stand in the pathway with sinners,</para>\n<para style="q1">or sit in the assembly of mockers.</para>\n<para style="q1">\n<verse number="2" style="v" />But his delight is in the law of Yahweh,</para>\n<para style="q1">and on his law he meditates day and night.\n<para style="q1">',
                        'lastvs': u'2',
                        'id': '01-01',
                        'img': '',
                        'format': 'usx'
                     },
                    {
                        'text': u'<verse number="3" style="v" />He will be like a tree planted by the streams of water</para>\n<para style="q1">that produces its fruit in its season,</para>\n<para style="q1">whose leaves do not wither;</para>\n<para style="q1">whatever he does will prosper.\n<para style="q1">',
                        'lastvs': u'3',
                        'id': '01-03',
                        'img': '',
                        'format': 'usx'
                    },
                    {
                        'text': u'<verse number="4" style="v" />The wicked are not so,</para>\n<para style="q1">but are instead like the chaff that the wind drives away.</para>',
                        'lastvs': u'4',
                        'id': '01-04',
                        'img': '',
                        'format': 'usx'
                    }
                ],
                'ref': '',
                'number': '01',
                'title': u'Capítulo 1'
            }
        ])

    def test_usx_to_json_chunks_and_s5(self, mock_reporter):
        #  TODO: this should ignore the s5 markers
        chunks = {
            '01': ['01', '03', '04']
        }

        usx = [
            u'<para style="mt">PSALMS</para>\n',
            u'<para style="cl">Psalm</para>\n',
            u'<note caller="u" style="s5"></note>\n',
            u'<para style="ms">Book One</para>\n',
            u'<chapter number="1" style="c" />\n',
            u'<para style="q1">\n',
            u'<verse number="1" style="v" />Blessed is the man who does not walk in the advice of the wicked,</para>\n',
            u'<para style="q1">or stand in the pathway with sinners,</para>\n',
            u'<para style="q1">or sit in the assembly of mockers.</para>\n',
            u'<para style="q1">\n',
            u'<verse number="2" style="v" />But his delight is in the law of Yahweh,</para>\n',
            u'<para style="q1">and on his law he meditates day and night.\n',
            u'<note caller="u" style="s5"></note>\n',
            u'<note caller="u" style="s5"></note></para>\n',
            u'<para style="q1">\n',
            u'<verse number="3" style="v" />He will be like a tree planted by the streams of water</para>\n',
            u'<para style="q1">that produces its fruit in its season,</para>\n',
            u'<para style="q1">whose leaves do not wither;</para>\n',
            u'<para style="q1">whatever he does will prosper.</para>\n',
            u'<para style="q1">\n',
            u'<verse number="4" style="v" />The wicked are not so,</para>\n',
            u'<para style="q1">but are instead like the chaff that the wind drives away.</para>\n',
        ]
        json = usx_to_chunked_json(usx, chunks, 'en', 'psa')
        self.assertEquals(json, [
            {
                'frames': [
                    {
                        'text': u'<para style="q1">\n<verse number="1" style="v" />Blessed is the man who does not walk in the advice of the wicked,</para>\n<para style="q1">or stand in the pathway with sinners,</para>\n<para style="q1">or sit in the assembly of mockers.</para>\n<para style="q1">\n<verse number="2" style="v" />But his delight is in the law of Yahweh,</para>\n<para style="q1">and on his law he meditates day and night.\n</para>\n<para style="q1">',
                        'lastvs': u'2',
                        'id': '01-01',
                        'img': '',
                        'format': 'usx'
                     },
                    {
                        'text': u'<verse number="3" style="v" />He will be like a tree planted by the streams of water</para>\n<para style="q1">that produces its fruit in its season,</para>\n<para style="q1">whose leaves do not wither;</para>\n<para style="q1">whatever he does will prosper.</para>\n<para style="q1">',
                        'lastvs': u'3',
                        'id': '01-03',
                        'img': '',
                        'format': 'usx'
                    },
                    {
                        'text': u'<verse number="4" style="v" />The wicked are not so,</para>\n<para style="q1">but are instead like the chaff that the wind drives away.</para>',
                        'lastvs': u'4',
                        'id': '01-04',
                        'img': '',
                        'format': 'usx'
                    }
                ],
                'ref': '',
                'number': '01',
                'title': ''
            }
        ])

    def test_index_tn_tsv_rc(self, mock_reporter):
        tmp = os.path.join(self.temp_dir, 'index_tn_rc')
        rc = os.path.join(self.resources_dir, 'en_tn_tsv')
        expected_file = os.path.join(self.resources_dir, 'en_tn_tsv/expected_gen_notes.json')
        converted_file = '{}/gen/en/notes.json'.format(tmp)
        expected = {
            'en_*_gen_tn': {
                'key': 'gen/en/notes.json',
                'path': converted_file
            }
        }

        to_upload = index_tn_rc('en', tmp, rc)
        self.assertEqual(expected, to_upload)
        self.assertEquals(read_file(expected_file), read_file(converted_file))

    def test_tn_tsv_to_json(self, mock_reporter):
        chunks = {
            '01': ['01', '03', '05'],
            '02': ['01', '04', '07'],
        }
        tsv = [
            {'Chapter': 'front', 'Verse': 'intro', 'GLQuote': '', 'OccurrenceNote': 'Book intro stuff'},
            {'Chapter': '1', 'Verse': 'intro', 'GLQuote': '', 'OccurrenceNote': 'Chapter intro stuff'},
            {'Chapter': '1', 'Verse': '1', 'GLQuote': 'in', 'OccurrenceNote': 'in notes'},
            {'Chapter': '1', 'Verse': '2', 'GLQuote': 'the', 'OccurrenceNote': 'the notes'},
            {'Chapter': '1', 'Verse': '3', 'GLQuote': 'beginning', 'OccurrenceNote': 'beginning notes'},
            {'Chapter': '1', 'Verse': '4', 'GLQuote': 'God', 'OccurrenceNote': 'God notes'},
            {'Chapter': '2', 'Verse': 'intro', 'GLQuote': 'Chapter Information', 'OccurrenceNote': 'Chapter 2 stuff'},
            {'Chapter': '2', 'Verse': '1', 'GLQuote': 'in', 'OccurrenceNote': 'in notes'},
            {'Chapter': '2', 'Verse': '2', 'GLQuote': 'the', 'OccurrenceNote': 'the notes'},
            {'Chapter': '2', 'Verse': '3', 'GLQuote': 'beginning', 'OccurrenceNote': 'beginning notes'},
            {'Chapter': '2', 'Verse': '4', 'GLQuote': 'God', 'OccurrenceNote': 'God notes'},
            {'Chapter': '2', 'Verse': '5', 'GLQuote': 'created', 'OccurrenceNote': 'created notes'},
        ]
        expected = [
            {
                'id': 'front-title',
                'tn': [
                    {'ref': 'General Information', 'text': 'Book intro stuff'}
                ]
            },
            {
                'id': '01-title',
                'tn': [
                    {'ref': 'General Information', 'text': 'Chapter intro stuff'},
                ]
            },
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
                'id': '02-title',
                'tn': [
                    {'ref': 'Chapter Information', 'text': 'Chapter 2 stuff'},
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
