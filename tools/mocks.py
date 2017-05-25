
class MockS3Handler:

    def __init__(self, bucket):
        self._uploads = {}

    def upload_file(self, path, key):
        self._uploads[key] = path

class MockDynamodbHandler(object):

    def __init__(self):
        self.last_inserted_item = None
        self.db = []

    def insert_item(self, item):
        self.last_inserted_item = item
        self.db.append(item)

