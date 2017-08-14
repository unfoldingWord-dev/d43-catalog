import os
from unittest import TestCase
from tools import csvtousfm3
from tools.file_utils import read_file

class TestCSVtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def test_convert_file(self):
        usfm = csvtousfm3.convert(lang='Gr',
                                  csv_file=os.path.join(self.resources_dir, 'input.csv'))

        self.assertIsInstance(usfm, list)
        self.assertEqual(2, len(usfm))
        for book in usfm:
            self.assertIsInstance(book['usfm'], unicode)
            expected_usfm = read_file(os.path.join(self.resources_dir, '{}_output.usfm'.format(book['id'])))
            self.assertIsInstance(expected_usfm, unicode)
            self.assertMultiLineEqual(expected_usfm, book['usfm'])

    def test_convert_line(self):
        input_row = {
            'UWORD': '\xce\xb2\xce\xb9\xce\xb2\xce\xbb\xce\xbf\xcf\x83',
            'UMEDIEVAL': '\xce\x92\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82',
            'MORPH': '....NFS',
            'MID': 'BHP',
            'SYN': 'N.',
            'LEXEME': '9760',
            'LEMMA': 'biblos',
            'VERSE': '010101',
            'ULEMMA': '\xce\xb2\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82',
            'LEX': '.',
            'WORD': 'biblos',
            'ORDER': '1'
        }
        output = '\w \xce\x92\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82|lemma="\xce\xb2\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82" strongs="G09760" x-morph="Gr,N,,,,,NFS,"\w*'.decode('utf-8')

        self.assertIsInstance(output, unicode)
        usfm3 = csvtousfm3.convert_row(lang='Gr',
                                       row=input_row)
        self.assertIsInstance(usfm3, unicode)
        self.assertEqual(output, usfm3)

    def test_convert_punctuated_line(self):
        input_row = {
            'UWORD': '\xce\xb2\xce\xb9\xce\xb2\xce\xbb\xce\xbf\xcf\x83',
            'UMEDIEVAL': '\xce\x92\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82,', # note the trailing comma
            'MORPH': '....NFS',
            'MID': 'BHP',
            'SYN': 'N.',
            'LEXEME': '9760',
            'LEMMA': 'biblos',
            'VERSE': '010101',
            'ULEMMA': '\xce\xb2\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82',
            'LEX': '.',
            'WORD': 'biblos',
            'ORDER': '1'
        }
        output = '\w \xce\x92\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82|lemma="\xce\xb2\xce\xaf\xce\xb2\xce\xbb\xce\xbf\xcf\x82" strongs="G09760" x-morph="Gr,N,,,,,NFS,"\w*,'.decode('utf-8') # note the trailing comma

        self.assertIsInstance(output, unicode)
        usfm3 = csvtousfm3.convert_row(lang='Gr',
                                       row=input_row)
        self.assertIsInstance(usfm3, unicode)
        self.assertEqual(output, usfm3)