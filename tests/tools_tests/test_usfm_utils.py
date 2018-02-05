# coding=utf-8
from __future__ import unicode_literals
import os
import shutil
import tempfile
from unittest import TestCase
from libraries.tools.file_utils import read_file
from libraries.tools.usfm_utils import usfm3_to_usfm2, simplify_strong, get_usfm3_word_strongs, parse_book_id, strip_word_data, convert_chunk_markers, tWPhrase, strip_tw_links


class TestUsfmUtils(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='test_tools_')

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_strip_usfm_word_data(self):
        input = u'\\v 1 Ce \\w qui|strong="G3739" \\w* \\w était|strong="G2258" x-morph="strongMorph:TG5713" \\w* \\w dès|strong="G575" \\w*'
        expected = u'\\v 1 Ce qui était dès'
        output = strip_word_data(input)
        self.assertEqual(expected, output)

    def test_parse_book_id(self):
        input = '\id 2SA 2 Samuel'
        id = parse_book_id(input)
        self.assertEqual('2SA', id)

    def test_strip_usfm_mixed_word_data(self):
        """
        This ensures we are correctly handling input that contains spaces on "blank" lines.
        :return:
        """
        input = u'''\\v 7  \\w Fils|strong="H1121"\\w* de \\w Javan|strong="H3120"\\w*: \\w Élischa|strong="H473"\\w*, \\w Tarsisa|strong="H8659"\\w*, \\w Kittim|strong="H3794"\\w* et \\w Rodanim|strong="H1721"\\w*.
  
\\s5
\\v 8  \\w Fils|strong="H1121"\\w* de \\w Cham|strong="H2526"\\w*: \\w Cusch|strong="H3568"\\w*, \\w Mitsraïm|strong="H4714"\\w*, \\w Puth|strong="H6316"\\w* et \\w Canaan|strong="H3667"\\w*. -
\\v 9  \\w Fils|strong="H1121"\\w* de \\w Cusch|strong="H3568"\\w*: \\w Saba|strong="H5434"\\w*, \\w Havila|strong="H2341"\\w*, \\w Sabta|strong="H5454"\\w*, \\w Raema|strong="H7484"\\w* et \\w Sabteca|strong="H5455"\\w*. -\\w Fils|strong="H1121"\\w* de \\w Raema|strong="H7484"\\w*: \\w Séba|strong="H7614"\\w* et \\w Dedan|strong="H1719"\\w*.
\\v 10  \\w Cusch|strong="H3568"\\w* \\w engendra|strong="H3205" x-morph="strongMorph:TH8804"\\w* \\w Nimrod|strong="H5248"\\w*; c'est lui qui \\w commença|strong="H2490" x-morph="strongMorph:TH8689"\\w* à être \\w puissant|strong="H1368"\\w* sur la \\w terre|strong="H776"\\w*. -'''
        expected = u'''\\v 7 Fils de Javan: Élischa, Tarsisa, Kittim et Rodanim.

\\s5
\\v 8 Fils de Cham: Cusch, Mitsraïm, Puth et Canaan. -
\\v 9 Fils de Cusch: Saba, Havila, Sabta, Raema et Sabteca. - Fils de Raema: Séba et Dedan.
\\v 10 Cusch engendra Nimrod; c'est lui qui commença à être puissant sur la terre. -'''
        output = strip_word_data(input)
        self.assertEqual(expected, output)

    def test_strip_word_data_large_string(self):
        input = u'''\\id 1CH
\\h PREMIER LIVRE DES CHRONIQUES
\\toc1 PREMIER LIVRE DES CHRONIQUES
\\toc2 1 Chroniques
\\toc3 1 Ch
\\mt1 LES LIVRES DES CHRONIQUES
\\mt1 PREMIER LIVRE DES CHRONIQUES

\\s5
\\c 1
\\p
\\v 1  \\w Adam|strong="H121"\\w*, \\w Seth|strong="H8352"\\w*, \\w Énosch|strong="H583"\\w*,
\\v 2  \\w Kénan|strong="H7018"\\w*, \\w Mahalaleel|strong="H4111"\\w*, \\w Jéred|strong="H3382"\\w*,
\\v 3  \\w Hénoc|strong="H2585"\\w*, \\w Metuschélah|strong="H4968"\\w*, \\w Lémec|strong="H3929"\\w*,
\\v 4  \\w Noé|strong="H5146"\\w*, \\w Sem|strong="H8035"\\w*, \\w Cham|strong="H2526"\\w* et \\w Japhet|strong="H3315"\\w*.

\\s5
\\v 5  \\w Fils|strong="H1121"\\w* de \\w Japhet|strong="H3315"\\w*: \\w Gomer|strong="H1586"\\w*, \\w Magog|strong="H4031"\\w*, \\w Madaï|strong="H4074"\\w*, \\w Javan|strong="H3120"\\w*, \\w Tubal|strong="H8422"\\w*, \\w Méschec|strong="H4902"\\w* et \\w Tiras|strong="H8494"\\w*. -
\\v 6  \\w Fils|strong="H1121"\\w* de \\w Gomer|strong="H1586"\\w*: \\w Aschkenaz|strong="H813"\\w*, \\w Diphat|strong="H7384"\\w* et \\w Togarma|strong="H8425"\\w*. -
\\v 7  \\w Fils|strong="H1121"\\w* de \\w Javan|strong="H3120"\\w*: \\w Élischa|strong="H473"\\w*, \\w Tarsisa|strong="H8659"\\w*, \\w Kittim|strong="H3794"\\w* et \\w Rodanim|strong="H1721"\\w*.

\\s5
\\v 8  \\w Fils|strong="H1121"\\w* de \\w Cham|strong="H2526"\\w*: \\w Cusch|strong="H3568"\\w*, \\w Mitsraïm|strong="H4714"\\w*, \\w Puth|strong="H6316"\\w* et \\w Canaan|strong="H3667"\\w*. -
\\v 9  \\w Fils|strong="H1121"\\w* de \\w Cusch|strong="H3568"\\w*: \\w Saba|strong="H5434"\\w*, \\w Havila|strong="H2341"\\w*, \\w Sabta|strong="H5454"\\w*, \\w Raema|strong="H7484"\\w* et \\w Sabteca|strong="H5455"\\w*. -\\w Fils|strong="H1121"\\w* de \\w Raema|strong="H7484"\\w*: \\w Séba|strong="H7614"\\w* et \\w Dedan|strong="H1719"\\w*.
\\v 10  \\w Cusch|strong="H3568"\\w* \\w engendra|strong="H3205" x-morph="strongMorph:TH8804"\\w* \\w Nimrod|strong="H5248"\\w*; c'est lui qui \\w commença|strong="H2490" x-morph="strongMorph:TH8689"\\w* à être \\w puissant|strong="H1368"\\w* sur la \\w terre|strong="H776"\\w*. -
'''
        expected = read_file(os.path.join(self.resources_dir, 'uwapi_1ch.usfm'))
        output = strip_word_data(input)
        self.assertEqual(expected, output)

    def test_get_usfm3_word_strongs(self):
        strong = get_usfm3_word_strongs('\w וַ​יְהִ֗י|lemma="הָיָה" strong="H1961" x-morph="He,C:Vqw3ms" \w*')
        self.assertEqual('H1961', strong)

    def test_simplify_strong(self):
        strong = simplify_strong('c:H1961')
        self.assertEqual('H1961', strong)

        strong = simplify_strong('a:c:H1961')
        self.assertEqual('H1961', strong)

        strong = simplify_strong('H1961a')
        self.assertEqual('H1961', strong)

        strong = simplify_strong('c:H1961a')
        self.assertEqual('H1961', strong)

    def test_strip_word_data_from_file(self):
        """
        This ensures we are correctly converting content to be used in the
        uW api. This content wasn't getting converted correctly in the past.
        :return:
        """
        input = read_file(os.path.join(self.resources_dir, 'apiv3_1ch.usfm'))
        expected = read_file(os.path.join(self.resources_dir, 'uwapi_1ch.usfm'))
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

    def test_strip_all_complex_tw_links(self):
        input = u'''
\w γενέσεως|lemma="γένεσις" strong="G10780" x-morph="Gr,N,,,,,GFS," \w*
\k-s | x-tw="rc://*/tw/dict/bible/kt/jesus"
\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," \w*
\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ" \w*
\k-e\*,
\w υἱοῦ|lemma="υἱός" strong="G52070" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/sonofgod"  x-tw="rc://*/tw/dict/bible/kt/son" \w*'''
        expected = u'''
\w γενέσεως|lemma="γένεσις" strong="G10780" x-morph="Gr,N,,,,,GFS," \w*
\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," \w*
\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," \w*
\w υἱοῦ|lemma="υἱός" strong="G52070" x-morph="Gr,N,,,,,GMS," \w*'''
        output = strip_tw_links(input)
        self.assertEqual(expected, output)

    def test_strip_some_complex_tw_links(self):
        links = ['rc://*/tw/dict/bible/kt/jesus', 'rc://*/tw/dict/bible/kt/sonofgod']
        input = u'''
\w γενέσεως|lemma="γένεσις" strong="G10780" x-morph="Gr,N,,,,,GFS," \w*
\k-s | x-tw="{}"
\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," \w*
\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ" \w*
\k-e\*,
\w υἱοῦ|lemma="υἱός" strong="G52070" x-morph="Gr,N,,,,,GMS," x-tw="{}"  x-tw="rc://*/tw/dict/bible/kt/son" \w*'''.format(links[0], links[1])
        expected = u'''
\w γενέσεως|lemma="γένεσις" strong="G10780" x-morph="Gr,N,,,,,GFS," \w*
\w Ἰησοῦ|lemma="Ἰησοῦς" strong="G24240" x-morph="Gr,N,,,,,GMS," \w*
\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ" \w*
\w υἱοῦ|lemma="υἱός" strong="G52070" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/son" \w*'''
        output = strip_tw_links(input, links)
        self.assertEqual(expected, output)

    def test_strip_all_tw_links(self):
        input = '\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," x-tw="rc://*/tw/dict/bible/kt/christ" x-tw="rc://*/tw/dict/bible/kt/jesus" \w*,'
        expected = '\w Χριστοῦ|lemma="χριστός" strong="G55470" x-morph="Gr,N,,,,,GMS," \w*,'
        output = strip_tw_links(input)
        self.assertEqual(expected, output)

    def test_strip_some_tw_links(self):
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