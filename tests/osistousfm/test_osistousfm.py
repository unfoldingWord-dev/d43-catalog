# coding=utf-8
import os
import logging
import xml.etree.ElementTree as ET
from unittest import TestCase
from libraries.cli import osistousfm3
from libraries.tools.file_utils import read_file
from mock import patch, MagicMock


class TestOSIStoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.lexicon = osistousfm3.indexLexicon(ET.parse(os.path.join(self.resources_dir, 'lexicon.xml')).getroot())

        # configure logger
        logger = logging.getLogger(osistousfm3.LOGGER_NAME)
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def test_get_xml_books(self):
        xml = """<div type="nothing">
    <div>
        <div type="book" note="invalid book"/>
        <div type="book">
            <div type="child"/>
        </div>
        <div type="book">
            <div type="child"/>
            <div type="book" note="invalid book">
                <div type="child"/>
            </div>
        </div>
    </div>
</div>"""

        books = osistousfm3.getXmlBooks(ET.fromstring(xml))
        self.assertEqual(2, len(books))
        for book in books:
            self.assertTrue(len(book) > 0)

    def test_convert_word(self):
        word = ET.fromstring('<w lemma="3068" n="0.1.1.0" morph="HNp">יְהוָ֜ה</w>')
        usfm = osistousfm3.convertWord(self.lexicon, word)
        self.assertEqual(u'\w יְהוָ֜ה|lemma="יְהֹוָה" strong="H03068" x-morph="He,Np" \w*', usfm)

    def test_convert_word_with_complex_strong(self):
        word = ET.fromstring('<w lemma="a/3068 b" n="0.1.1.0" morph="HNp">יְהוָ֜ה</w>')
        usfm = osistousfm3.convertWord(self.lexicon, word)
        self.assertEqual(u'\w יְהוָ֜ה|lemma="יְהֹוָה" strong="a:H03068b" x-morph="He,Np" \w*', usfm)

    def test_convert_word_missing_morph(self):
        word = ET.fromstring('<w lemma="3068" n="0.1.1.0">יְהוָ֜ה</w>')
        usfm = osistousfm3.convertWord(self.lexicon, word)
        self.assertEqual(u'\w יְהוָ֜ה|lemma="יְהֹוָה" strong="H03068" \w*', usfm)

    def test_parse_strong_normal(self):
        strong, formatted = osistousfm3.parseStrong('3027')
        self.assertEqual('3027', strong)
        self.assertEqual('H03027', formatted)

    def test_parse_strong_with_prefix(self):
        strong, formatted = osistousfm3.parseStrong('b/3027')
        self.assertEqual('3027', strong)
        self.assertEqual('b:H03027', formatted)

    def test_parse_strong_with_multiple_prefix(self):
        strong, formatted = osistousfm3.parseStrong('a/b/3027')
        self.assertEqual('3027', strong)
        self.assertEqual('a:b:H03027', formatted)

    def test_parse_strong_with_suffix(self):
        strong, formatted = osistousfm3.parseStrong('3027 a')
        self.assertEqual('3027', strong)
        self.assertEqual('H03027a', formatted)

    def test_parse_strong_with_multiple_suffix(self):
        strong, formatted = osistousfm3.parseStrong('3027 a b')
        self.assertEqual('3027', strong)
        self.assertEqual('H03027ab', formatted)

    def test_parse_strong_suffix_and_prefix(self):
        strong, formatted = osistousfm3.parseStrong('a/3027 b')
        self.assertEqual('3027', strong)
        self.assertEqual('a:H03027b', formatted)

    def test_convert_file(self):
        usfm = osistousfm3.convertFile(osis_file=os.path.join(self.resources_dir, 'osis/Hag.xml'),
                                    lexicon=self.lexicon)
        expected_usfm = read_file(os.path.join(self.resources_dir, 'usfm/37-HAG.usfm'))
        self.assertEqual(expected_usfm, usfm)

    def test_get_unknown_lemma(self):
        lexicon = None
        lemma = osistousfm3.getLemma(lexicon, 'H1')
        self.assertIsNone(lemma)

    def test_get_lemma(self):
        lemma = osistousfm3.getLemma(self.lexicon, 'H2')
        self.assertEqual(u'אַב', lemma)

    @patch('libraries.cli.osistousfm3.write_file')
    def test_convert_dir(self, mock_write_file):
        mock_write_file.return_value = MagicMock(name='write_file')
        in_dir = os.path.join(self.resources_dir, 'osis')
        out_dir = os.path.join(self.resources_dir, 'nothing')
        lex_path = os.path.join(self.resources_dir, 'lexicon.xml')
        osistousfm3.convertDir(in_dir, out_dir, lex_path)
        mock_write_file.assert_called()
        self.assertEqual(2, mock_write_file.call_count)