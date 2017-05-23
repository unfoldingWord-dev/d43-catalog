
class MockS3Handler:

    def __init__(self):
        self.uploads = []

    def upload_file(self, path, key):
        self.uploads.append({
            'key': key,
            'path': path
        })

class MockDynamodbHandler(object):

    def __init__(self):
        self.last_inserted_item = None
        self.db = []

    def insert_item(self, item):
        self.last_inserted_item = item
        self.db.append(item)