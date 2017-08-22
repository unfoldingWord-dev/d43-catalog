from d43_aws_tools import DynamoDBHandler
import os
import tempfile
import shutil
import arrow

def is_lambda_running(context, dbname, lambda_suffix=None, dynamodb_handler=None):
    """
    Retrieves the last recorded process information for this lambda.
    This is used to determine if the lambda is already running.
    :param context:
    :param string dbname: the database holding a list of lambda run times
    :param string lambda_suffix: name of the lambda handler
    :return:
    """
    if not context:
        return False
    if dynamodb_handler:
        db = dynamodb_handler(dbname)
    else:
        db = DynamoDBHandler(dbname)

    lambda_name = context.function_name
    if lambda_suffix:
        lambda_name = '{}.{}'.format(lambda_name, lambda_suffix)

    request = db.get_item({
        "lambda": lambda_name
    })
    if request:
        last_time = arrow.get(request['started_at']).to('local')
        # TRICKY: we use this lambda's expires time instead of the recorded value avoid delays in applying changes to expiration times.
        timeout = arrow.now().shift(minutes=-lambda_min_remaining(context))
        return last_time > timeout
    else:
        return False

def lambda_min_remaining(context):
    """
    Returns the time remaining in minutes before the lambda times out
    :param context:
    :return:
    """
    time_remaining = context.get_remaining_time_in_millis() / 60000  # ms to min
    return time_remaining

def set_lambda_running(context, dbname, lambda_suffix=None, dynamodb_handler=None):
    """
    Sets the process information for this lambda.
    This is used to indicate the lambda is currently running.
    :param context:
    :param string dbname: the database holding a list of lambda run times.
    :param string lambda_suffix: name of the lambda handler
    :return:
    """
    if not context:
        return
    if dynamodb_handler:
        db = dynamodb_handler(dbname)
    else:
        db = DynamoDBHandler(dbname)

    lambda_name = context.function_name
    if lambda_suffix:
        lambda_name = '{}.{}'.format(lambda_name, lambda_suffix)

    db.insert_item({
        "lambda": lambda_name,
        "request_id": context.aws_request_id,
        "started_at": arrow.utcnow().isoformat(),
        "expires": context.get_remaining_time_in_millis()
    })

def clear_lambda_running(context, dbname, lambda_suffix=None, dynamodb_handler=None):
    """
    This is a convenience method to clear a lambda from the list of running lambdas
    :param context:
    :param string dbname:
    :param string lambda_suffix: the name of the lambda handler
    :param dynamodb_handler:
    :return:
    """
    if dynamodb_handler:
        db = dynamodb_handler(dbname)
    else:
        db = DynamoDBHandler(dbname)

    lambda_name = context.function_name
    if lambda_suffix:
        lambda_name = '{}.{}'.format(lambda_name, lambda_suffix)


    db.delete_item({
        "lambda": lambda_name
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