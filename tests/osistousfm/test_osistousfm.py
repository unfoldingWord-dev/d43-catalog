# coding=utf-8
import os
import logging
import xml.etree.ElementTree as ET
from unittest import TestCase
from libraries.cli import osistousfm3
from libraries.tools.file_utils import read_file


class TestOSIStoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
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

    def test_convert_file(self):
        lexicon = ET.parse(os.path.join(self.resources_dir, 'lexicon.xml')).getroot()
        usfm = osistousfm3.convertFile(osis_file=os.path.join(self.resources_dir, 'osis/Hag.xml'),
                                    lexicon=lexicon)
        expected_usfm = read_file(os.path.join(self.resources_dir, 'usfm/37-HAG.usfm'))
        self.assertEqual(expected_usfm, usfm)

    def test_get_unknown_lemma(self):
        lexicon = None
        lemma = osistousfm3.getLemma(lexicon, 'H1')
        self.assertIsNone(lemma)

    def test_get_lemma(self):
        lexicon = ET.parse(os.path.join(self.resources_dir, 'lexicon.xml')).getroot()
        lemma = osistousfm3.getLemma(lexicon, 'H2')
        self.assertEqual(u'אַב', lemma)