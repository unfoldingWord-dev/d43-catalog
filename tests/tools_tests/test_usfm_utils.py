# coding=utf-8
import os
import shutil
import tempfile
from unittest import TestCase
from libraries.tools.file_utils import read_file
from libraries.tools.usfm_utils import usfm3_to_usfm2, strip_word_data, convert_chunk_markers, tWPhrase, strip_tw_links


class TestUsfmUtils(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='test_tools_')

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_strip_usfm_word_data(self):
        input = '\\v 1 Ce \w qui|strong="G3739"\w* \w était|strong="G2258" x-morph="strongMorph:TG5713"\w* \w dès|strong="G575"\w*'
        expected = '\\v 1 Ce qui était dès'
        output = strip_word_data(input)
        self.assertEqual(expected, output)

    def test_tw_phrase_print(self):
        phrase = tWPhrase(1)
        phrase.addLine(u'\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/jesus" \w*')
        phrase.addLine(u'\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ"  x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,')

        expected = read_file(os.path.join(self.resources_dir, 'usfm_milestone.usfm'))
        self.assertEqual(unicode(expected), unicode(phrase))

    def test_convert_chunk_markers(self):
        input = '\\ts\n\\v 1 Ce qui était dès\n\\ts\n\\v 2 Ce qui était dès'
        expected = '\\s5\n\\v 1 Ce qui était dès\n\\s5\n\\v 2 Ce qui était dès'
        output = convert_chunk_markers(input)
        self.assertEqual(expected, output)

    def test_strip_some_tw_link(self):
        links = ['rc://*/tw/dict/bible/kt/jesus', 'rc://*/tw/dict/bible/kt/test']
        input = '\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ" x-tw="{}" x-tw="{}" \w*,'.format(links[0], links[1])
        expected = '\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ" \w*,'
        output = strip_tw_links(input, links)
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

    def test_usfm3_to_usfm2(self):
        usfm3 = read_file(os.path.join(self.resources_dir, 'usfm3_sample.usfm'))
        expected_usfm2 = read_file(os.path.join(self.resources_dir, 'usfm2_sample.usfm'))

        usfm2 = usfm3_to_usfm2(usfm3)
        self.assertEqual(expected_usfm2, usfm2)