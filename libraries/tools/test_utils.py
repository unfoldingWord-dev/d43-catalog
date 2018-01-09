from __future__ import print_function, unicode_literals
import json
import os
from file_utils import read_file


def sort_object(obj):
    """
    Sorts the values in an object
    :param obj:
    :return:
    """
    if isinstance(obj, dict):
        return sorted((k, sort_object(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(sort_object(x) for x in obj)
    else:
        return obj


def assert_object_equals_file(unit_test, obj, path):
    """
    Asserts that an object equals the contents of a json file
    :param unit_test:
    :param obj:
    :param path:
    :return:
    """
    expected_obj = json.loads(read_file(path))
    assert_object_equals(unit_test, expected_obj, obj)

def assert_json_files_equal(unit_test, path1, path2):
    """
    Asserts that two files containing json are equal
    :param unit_test:
    :param path1:
    :param path2:
    :return:
    """
    obj1 = json.loads(read_file(path1))
    obj2 = json.loads(read_file(path2))
    assert_object_equals(unit_test, obj1, obj2)

def assert_object_equals(unit_test, obj1, obj2):
    """
    Checks if two objects are equal after recursively sorting them
    :param unit_test: the object doing the assertions
    :param obj1:
    :param obj2:
    :return:
    """
    unit_test.assertTrue(object_equals(obj1, obj2))

def object_equals(obj1, obj2):
    """
        Checks if two objects are equal after recursively sorting them
        :param unit_test: the object doing the assertions
        :param obj1:
        :param obj2:
        :return:
        """
    return sort_object(obj1) == sort_object(obj2)

def assert_object_not_equals(unit_test, obj1, obj2):
    """
    Checks if two objects are not equal after recursively sorting them
    :param unit_test: the object doing the assertions
    :param obj1:
    :param obj2:
    :return:
    """
    unit_test.assertNotEqual(sort_object(obj1), sort_object(obj2))


def assert_s3_equals_api_json(unit_test, mock_s3, mock_api, key):
    """
    Asserts that the s3 file identified by the given key matches
    the equivalent file in the api
    :param unit_test: an instance of UnitTest
    :param mock_s3:
    :param mock_api:
    :param key: the relative path to the key
    :return:
    """
    unit_test.assertIn(key, mock_s3._recent_uploads)
    s3_obj = json.loads(read_file(mock_s3._recent_uploads[key]))
    api_obj = json.loads(mock_api.get_url(key))
    assert_object_equals(unit_test, s3_obj, api_obj)

def assert_s3_equals_api_text(unit_test, mock_s3, mock_api, key):
    """
    Asserts that the s3 file identified by the given key matches
    the equivalent file in the api
    :param unit_test: an instance of UnitTest
    :param mock_s3:
    :param mock_api:
    :param key: the relative path to the key
    :return:
    """
    unit_test.assertIn(key, mock_s3._recent_uploads)
    s3_text = read_file(mock_s3._recent_uploads[key])
    api_text = mock_api.get_url(key)
    unit_test.assertEquals(s3_text, api_text)


def is_travis():
    """
    Checks if the current environment is travis
    :return:
    """
    return 'TRAVIS' in os.environ and os.environ['TRAVIS'] == 'true'

class Bunch:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)