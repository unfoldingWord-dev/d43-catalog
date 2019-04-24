from libraries.tools.versification import  hebrew_to_ufw
from unittest import TestCase

class TestVersification(TestCase):

    def test_joel_3_1(self):
        ref = hebrew_to_ufw('jol', 3, 1)
        expected = {'book': 'jol', 'chapter': 2, 'verse': 28}
        self.assertEqual(expected, ref.to_dict())
