# coding=utf-8
import os
from unittest import TestCase

from libraries.cli import osistousfm3
from libraries.tools.file_utils import read_file


class TestCSVtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def test_convert_file(self):
        usfm = osistousfm3.convertFile(lang='Heb',
                                   osis_file=os.path.join(self.resources_dir, 'osis/1Chr.xml'))
        self.assertEqual('', usfm)