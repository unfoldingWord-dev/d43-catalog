import arrow
import time

def unix_to_timestamp(timeint):
    """
    Converts a unix time value to a standardized UTC based timestamp
    :param datestring:
    :return:
    """
    d = arrow.get(timeint).to('local').datetime
    return d.isoformat()
    # datetime.datetime.fromtimestamp(stats.st_mtime).isoformat()

def str_to_timestamp(datestring):
    """
    Converts a datetime string to a standardized UTC based timestamp
    :param datestring:
    :return:
    """
    # TRICKY: time.mktime expects local time so we convert to local tz
    d = arrow.get(datestring).to('local').to('utc').datetime
    return d.isoformat()

def str_to_unix_time(datestring):
    """
    Converts a datetime string to a unix timestamp
    :param datestring: a datetime string formatted according to ISO 8601
    :return:
    """
    # TRICKY: time.mktime expects local time so we convert to local tz
    d = arrow.get(datestring).to('local').datetime
    return str(int(time.mktime(d.timetuple())))