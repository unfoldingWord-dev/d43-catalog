# coding=utf-8
import os
import shutil
import tempfile
import unittest
from libraries.tools.test_utils import is_travis, Bunch
from unittest import TestCase

from libraries.tools.usfm_utils import strip_word_data, convert_chunk_markers, tWPhrase
from libraries.tools.build_utils import get_build_rules
from libraries.tools.mocks import MockDynamodbHandler
from libraries.tools.lambda_utils import wipe_temp, is_lambda_running, set_lambda_running, clear_lambda_running, lambda_min_remaining
from libraries.tools.file_utils import read_file


class TestTools(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

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

    def test_strip_usfm_word_data(self):
        input = '\\v 1 Ce \w qui|strong="G3739"\w* \w était|strong="G2258" x-morph="strongMorph:TG5713"\w* \w dès|strong="G575"\w*'
        expected = '\\v 1 Ce qui était dès'
        output = strip_word_data(input)
        self.assertEqual(expected, output)

    def test_convert_chunk_markers(self):
        input = '\\ts\n\\v 1 Ce qui était dès\n\\ts\n\\v 2 Ce qui était dès'
        expected = '\\s5\n\\v 1 Ce qui était dès\n\\s5\n\\v 2 Ce qui était dès'
        output = convert_chunk_markers(input)
        self.assertEqual(expected, output)

    def test_tw_phrase_validate_empty(self):
        phrase = tWPhrase(1)
        self.assertTrue(phrase.isLineValid('\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/jesus" \w*'))
        self.assertTrue(phrase.isLineValid('\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ"  x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,'))
        self.assertFalse(phrase.isLineValid('\w δοῦλος|lemma="δοῦλος" strong="G14010" x-morph="Gr,N,,,,,NMS,"\w*'))

    def test_tw_phrase_validate_filled(self):
        phrase = tWPhrase(1)
        phrase.addLine('\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ"  x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,')

        self.assertFalse(phrase.isLineValid('\w δοῦλος|lemma="δοῦλος" strong="G14010" x-morph="Gr,N,,,,,NMS,"\w*'))
        self.assertTrue(phrase.isLineValid('\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ"  x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,'))
        self.assertFalse(phrase.isLineValid('\w Θεοῦ|lemma="θεός" strong="G23160" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/god"  x-tw="rc://*/tw/dict/bible/kt/godly" \w*,'))

    def test_tw_phrase_add(self):
        phrase = tWPhrase(1)
        phrase.addLine('\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ"  x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,')
        self.assertEqual(1, len(phrase.lines()))
        self.assertEqual(2, len(phrase.links()))

        # TRICKY: adding word with only one common link will reduce link set
        phrase.addLine('\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/jesus" \w*')
        self.assertEqual(2, len(phrase.lines()))
        self.assertEqual(1, len(phrase.links()))

    def test_tw_phrase_print(self):
        phrase = tWPhrase(1)
        phrase.addLine('\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/jesus" \w*')
        phrase.addLine('\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ"  x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,')

        expected = read_file(os.path.join(self.resources_dir, 'usfm_milestone.usfm'))
        self.assertEqual(expected, unicode(str(phrase), 'utf-8'))

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
