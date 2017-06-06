from general_tools.file_utils import load_json_object

class MockS3Handler:

    def __init__(self, bucket):
        self._uploads = {}

    def upload_file(self, path, key):
        self._uploads[key] = path

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
        self.db = load_json_object(path, {})

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