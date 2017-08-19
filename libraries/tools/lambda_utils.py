from d43_aws_tools import DynamoDBHandler
import time
import os
import tempfile
import shutil
import arrow

def lambda_restarted(context, dbname='d43-catalog-requests'):
    """
    THIS IS DEPRECATED!!!!
    Checks if the lambda instance is a restart.
    Restarts may occur if an instance encountered an exception or timed out.

    :param context: the lambda context
    :param dbname: the dynamo db where lambda request ids are stored for recollection.
    :return: True if the instance restarted or False if starting for the first time.
    """
    if not context:
        return False
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

def is_lambda_running(context, dbname, dynamodb_handler=None):
    """
    Retrieves the last recorded process information for this lambda.
    This is used to determine if the lambda is already running.
    :param context:
    :param dbname: the database holding a list of lambda run times
    :return:
    """
    if not context:
        return False
    if dynamodb_handler:
        db = dynamodb_handler(dbname)
    else:
        db = DynamoDBHandler(dbname)
    request = db.get_item({
        "lambda": context.function_name
    })
    if request:
        last_time = arrow.get(request['started_at']).to('local')
        timeout = arrow.now().shift(minutes=-5)
        return last_time > timeout
    else:
        return False


def set_lambda_running(context, dbname, dynamodb_handler=None):
    """
    Sets the process information for this lambda.
    This is used to indicate the lambda is currently running.
    :param context:
    :param dbname: the database holding a list of lambda run times.
    :return:
    """
    if not context:
        return
    if dynamodb_handler:
        db = dynamodb_handler(dbname)
    else:
        db = DynamoDBHandler(dbname)
    db.insert_item({
        "lambda": context.function_name,
        "request_id": context.aws_request_id,
        "started_at": arrow.utcnow().isoformat()
    })

def clear_lambda_running(context, dbname, dynamodb_handler=None):
    """
    This is a convenience method to clear a lambda from the list of running lambdas
    :param context:
    :param dbname:
    :param dynamodb_handler:
    :return:
    """
    if dynamodb_handler:
        db = dynamodb_handler(dbname)
    else:
        db = DynamoDBHandler(dbname)
    db.delete_item({
        "lambda": context.function_name
    })


def wipe_temp(tmp_dir=None, ignore_errors=False):
    """
    This will delete everything in the /tmp directory.
    Lambda instances may be reused and if a lambda timed out the temp files may not have been removed.
    Running this method will remove all temp files on the instance
    :param string tmp_dir:
    :param bool ignore_errors:
    :return:
    """
    if not tmp_dir:
        tmp_dir = tempfile.gettempdir()

    # TRICKY: gettempdir() could return None
    if tmp_dir:
        files = os.listdir(tmp_dir)
        for f in files:
            if f in ['.', '..']: continue

            f_path = os.path.join(tmp_dir, f)
            if os.path.isdir(f_path):
                shutil.rmtree(f_path, ignore_errors)
            elif os.path.isfile(f_path):
                os.unlink(f_path)