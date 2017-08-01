from tools.file_utils import load_json_object
import shutil
import tempfile
import os
import codecs
from consistency_checker import ConsistencyChecker

class MockAPI(object):
    """
    Creates a mock static api
    """

    def __init__(self, dir=None, mock_host=None):
        self.hosts = {}
        if  dir and mock_host:
            self.add_host(dir, mock_host)

    def add_host(self, dir, mock_host):
        """
        Adds a new host definition to the mock api
        :param dir:
        :param mock_host:
        :return:
        """
        if not os.path.isdir(dir):
            raise Exception('MockAPI: api directory not found at {}'.format(dir))
        if not mock_host.strip():
            raise Exception('MockAPI: invalid host value')

        self.hosts[mock_host.rstrip('/')] = dir

    def get_url(self, url, catch_exception=False):
        """
        Reads the contents of the url and returns it
        :param path:
        :return:
        """
        host_dir = self._get_host_dir(url)
        path = os.path.join(host_dir, self._strip_host(url))
        if catch_exception:
            try:
                with codecs.open(path, 'r', encoding='utf-8-sig') as f:
                    response = f.read()
            except:
                response = False
        else:
            if os.path.isfile(path):
                with codecs.open(path, 'r', encoding='utf-8-sig') as f:
                    response = f.read()
            else:
                raise Exception('404: {}'.format(url))

        # convert bytes to str (Python 3.5)
        if type(response) is bytes:
            return response.decode('utf-8')
        else:
            return response

    def url_exists(self, url):
        """
        Checks if a url exists within the mock api
        :param url:
        :return:
        """
        host_dir = self._get_host_dir(url)
        path = os.path.join(host_dir, self._strip_host(url))
        return os.path.exists(path)

    def download_file(self, url, dest):
        """
        Downloads the contents of the url to a file
        :param path:
        :param dest:
        :return:
        """
        host_dir = self._get_host_dir(url)
        path = os.path.join(host_dir, self._strip_host(url)).encode('utf-8')
        if os.path.isfile(path):
            shutil.copyfile(path, dest)
        else:
            raise Exception('404: {}'.format(url))

    def _strip_host(self, url):
        """
        Removes the host from the api url
        :param url:
        :return:
        """
        for host in self.hosts:
            if url.startswith(host):
                return url[len(host):].lstrip('/')
        return url.lstrip('/')

    def _get_host_dir(self, url):
        """
        Retrieves the host dir that matches the given url
        :param url:
        :return:
        """
        for host in self.hosts:
            if url.startswith(host):
                return self.hosts[host]
        # default to only host if no prefix is found
        if not url.startswith('http') and len(self.hosts) == 1:
            for host in self.hosts:
                return self.hosts[host]

        raise Exception('MockAPI: No host defined for {}'.format(url))

class MockLogger(object):

    def __init__(self):
        self._messages = []

    def warning(self, message):
        print('WARNING: {}'.format(message))
        self._messages.append(message)


class MockS3Handler:

    def __init__(self, bucket=None):
        self.__uploads = {}
        """a list of files available in the mock"""
        self._recent_uploads = {}
        """a list of files that have been recently uploaded. You should usually use this in tests"""
        self.temp_dir = tempfile.mkdtemp()

    def __del__(self):
        shutil.rmtree(self.temp_dir)

    def _load_path(self, dir, root=None):
        """
        Loads all the files in the path into the mock handler.
        Files loaded int his way way will not appear in the list of recently uploaded files. a.k.a. won't influence tests
        :param dir:
        :param root: the path that serves at the root of the file space
        :return:
        """
        upload_history = self._recent_uploads.copy()
        if not root:
            root = dir

        files = os.listdir(dir)
        for f in files:
            path = os.path.join(dir, f)
            if os.path.isfile(path):
                key = path[len(root):].lstrip('/\\')
                self.upload_file(path, key)
            else:
                self._load_path(path, root)
        self._recent_uploads = upload_history

    def upload_file(self, path, key, cache_time=600):
        upload_path = os.path.join(self.temp_dir, key)
        parent_dir = os.path.dirname(upload_path)
        if not os.path.isdir(parent_dir):
            os.makedirs(parent_dir)

        shutil.copy(path, upload_path)
        self.__uploads[key] = upload_path
        self._recent_uploads[key] = upload_path

    def download_file(self, key, path):
        if key in self.__uploads:
            shutil.copy(self.__uploads[key], path)
        else:
            raise Exception('File not found for key: {}'.format(key))

    def delete_file(self, key, catch_exception=True):
        if catch_exception:
            try:
                os.remove(self.__uploads[key])
            except:
                return False
        else:
            os.remove(self.__uploads[key])
            return True

class MockDynamodbHandler(object):

    def __init__(self, table_name=None):
        self._last_inserted_item = None
        self._db = []

    def _load_db(self, path):
        """
        Loads the test database. This must be a json file.
        :param path: the path to the test db file
        :return:
        """
        if os.path.isfile(path):
            self._db = load_json_object(path, {})
        else:
            raise Exception('Missing mock database path {}'.format(path))

    def insert_item(self, item):
        self._last_inserted_item = item
        self._db.append(item)

    def update_item(self, record_keys, row):
        self._last_inserted_item = row
        item = self.get_item(record_keys)
        if not item: return False
        item.update(row)
        return True

    def get_item(self, record_keys):
        for item in self._db:
            if MockDynamodbHandler._has_keys(item, record_keys):
                return item

        return None

    def query_items(self, query=None, only_fields_with_values=True):
        items = []
        for item in self._db:
            if not query:
                items.append(item)
            elif MockDynamodbHandler._has_keys(item, query):
                items.append(item)
        return items

    def delete_item(self, query):
        items = []
        for item in self._db:
            if not query or not MockDynamodbHandler._has_keys(item, query):
                items.append(item)
        self._db = items

    @staticmethod
    def _has_keys(obj, keys):
        """
        Checks if an object contains a list of keys and values
        :param obj:
        :param keys: a list of keys and values
        :return:
        """
        if not keys: return False
        for key in keys:
            if key not in obj:
                return False

            value = keys[key]
            if isinstance(value, dict) and 'condition' in value and 'value' in value and isinstance(value['value'], list):
                if value['condition'] == 'is_in':
                    was_in = False
                    for v in value['value']:
                        if obj[key] == v:
                            was_in = True
                            break
                    if not was_in:
                        return False
            elif obj[key] != value:
                return False

        return True

class MockSESHandler(object):
    pass

class MockSigner(object):

    def __init__(self, priv_pem_path=None, pub_pem_path=None):
        self.__should_fail_signing = False
        self.__should_fail_verification = False

    def sign_file(self, file_to_sign, private_pem_file=None):
        if self.__should_fail_signing:
            raise Exception('Mock signing failed')

        if not os.path.exists(file_to_sign):
            raise Exception('File does not exist {}'.format(file_to_sign))

        sig_file_name = '{}.sig'.format(file_to_sign)
        open(sig_file_name, 'a').close()
        return sig_file_name

    def verify_signature(self, content_file, sig_file, public_pem_file=None):
        if self.__should_fail_verification:
            raise RuntimeError('Mock verification failed')

        if not os.path.exists(content_file):
            raise Exception('File does not exist {}'.format(content_file))

        return True

    def _fail_signing(self, should_fail=True):
        """
        sets whether signing should fail
        :param should_fail:
        :return:
        """
        self.__should_fail_signing = should_fail

    def _fail_verification(self, should_fail=True):
        """
        sets whether verification should fail
        :param should_fail:
        :return:
        """
        self.__should_fail_verification = should_fail

class MockChecker(ConsistencyChecker):

    def __init__(self, quiet=False):
        super(MockChecker, self).__init__(quiet)
        self._urls_do_exist = True

    def _url_exists(self, url):
        return self._urls_do_exist