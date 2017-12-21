# coding=utf-8
import os
import xml.etree.ElementTree as ET
from unittest import TestCase
from libraries.cli import osistousfm3
from libraries.tools.file_utils import read_file


class TestCSVtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

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
        usfm = osistousfm3.convertFile(lang='Heb',
                                   osis_file=os.path.join(self.resources_dir, 'osis/Hag.xml'))
        expected_usfm = read_file(os.path.join(self.resources_dir, 'usfm/37-HAG.usfm'))
        self.assertEqual(expected_usfm, usfm)