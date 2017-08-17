from d43_aws_tools import DynamoDBHandler
import time

def lambda_restarted(context, dbname='d43-catalog-requests'):
    """
    Checks if the lambda instance is a restart.
    Restarts may occur if an instance encountered an exception or timed out.

    :param context: the lambda context
    :param dbname: the dynamo db where lambda request ids are stored for recollection.
    :return: True if the instance restarted or False if starting for the first time.
    """
    db = DynamoDBHandler('d43-catalog-requests')

    request = db.get_item({
        "request_id": context.aws_request_id
    })
    if request:
        return True
    else:
        # record id so we can detect restarts
        db.insert_item({
            "request_id": context.aws_request_id,
            "name": context.function_name,
            "version": context.function_version,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })
        return False
