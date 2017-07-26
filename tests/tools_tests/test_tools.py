from unittest import TestCase
from tools.build_utils import get_build_rules


class TestTools(TestCase):

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