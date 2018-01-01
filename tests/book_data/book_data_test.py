from unittest import TestCase
from libraries.tools.book_data import get_book_by_osis_id, get_book_by_sort

class TestBookData(TestCase):

    def test_get_book_by_osis_id(self):
        genBook = get_book_by_osis_id('Gen')
        self.assertEqual('01', genBook['sort'])
        self.assertEqual('GEN', genBook['usfm_id'])
        self.assertEqual('Gen', genBook['osis_id'])
        self.assertEqual('Genesis', genBook['en_name'])

        malBook = get_book_by_osis_id('Mal')
        self.assertEqual('39', malBook['sort'])
        self.assertEqual('MAL', malBook['usfm_id'])
        self.assertEqual('Mal', malBook['osis_id'])
        self.assertEqual('Malachi', malBook['en_name'])

    def test_get_book_by_sort(self):
        genBook = get_book_by_sort('01')
        self.assertEqual('01', genBook['sort'])
        self.assertEqual('GEN', genBook['usfm_id'])
        self.assertEqual('Gen', genBook['osis_id'])
        self.assertEqual('Genesis', genBook['en_name'])

        malBook = get_book_by_sort('39')
        self.assertEqual('39', malBook['sort'])
        self.assertEqual('MAL', malBook['usfm_id'])
        self.assertEqual('Mal', malBook['osis_id'])
        self.assertEqual('Malachi', malBook['en_name'])