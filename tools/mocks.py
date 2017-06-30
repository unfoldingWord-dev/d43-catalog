from tools.file_utils import load_json_object
import shutil
import tempfile
import os
import codecs

class MockAPI(object):
    """
    Creates a mock static api
    """

    def __init__(self, dir, mock_host):
        self.dir = dir
        self.host = mock_host.rstrip('/')
        if not os.path.isdir(dir):
            raise Exception('MockAPI: api directory not found at {}'.format(dir))

    def get_url(self, url, catch_exception=False):
        """
        Reads the contents of the url and returns it
        :param path:
        :return:
        """
        path = os.path.join(self.dir, self._strip_host(url))
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

    def download_file(self, url, dest):
        """
        Downloads the contents of the url to a file
        :param path:
        :param dest:
        :return:
        """
        path = os.path.join(self.dir, self._strip_host(url))
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
        if url.startswith(self.host):
            return url[len(self.host):].lstrip('/')
        return url.lstrip('/')

class MockLogger(object):
    @staticmethod
    def warning(message):
        print('WARNING: {}'.format(message))


class MockS3Handler:

    def __init__(self, bucket):
        self._uploads = {}
        self.temp_dir = tempfile.mkdtemp()

    def __del__(self):
        shutil.rmtree(self.temp_dir)

    def upload_file(self, path, key):
        upload_path = os.path.join(self.temp_dir, key)
        parent_dir = os.path.dirname(upload_path)
        if not os.path.isdir(parent_dir):
            os.makedirs(parent_dir)

        shutil.copy(path, upload_path)
        self._uploads[key] = upload_path

    def download_file(self, key, path):
        if key in self._uploads:
            shutil.copy(self._uploads[key], path)
        else:
            raise Exception('File not found for key: {}'.format(key))

class MockDynamodbHandler(object):

    def __init__(self, table_name=None):
        self.last_inserted_item = None
        self.db = []

    def _load_db(self, path):
        """
        Loads the test database. This must be a json file.
        :param path: the path to the test db file
        :return:
        """
        if os.path.isfile(path):
            self.db = load_json_object(path, {})
        else:
            raise Exception('Missing mock database path {}'.format(path))

    def insert_item(self, item):
        self.last_inserted_item = item
        self.db.append(item)

    def update_item(self, record_keys, row):
        self.last_inserted_item = row
        item = self.get_item(record_keys)
        if not item: return False
        item.update(row)
        return True

    def get_item(self, record_keys):
        for item in self.db:
            if MockDynamodbHandler._has_keys(item, record_keys):
                return item

        return None

    def query_items(self, query=None, only_fields_with_values=True):
        items = []
        for item in self.db:
            if not query:
                items.append(item)
            elif MockDynamodbHandler._has_keys(item, query):
                items.append(item)
        return items

    def delete_item(self, query):
        items = []
        for item in self.db:
            if not query or not MockDynamodbHandler._has_keys(item, query):
                items.append(item)
        self.db = items

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
            if key not in obj or obj[key] != keys[key]:
                return False

        return True