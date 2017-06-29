def read_dict(dictionary, key, dict_name=None):
    """
    Retrieves a value from a dictionary, raising an error message if the
    specified key is not valid
    :param dict dictionary:
    :param any key:
    :param str|unicode dict_name: name of dictionary, for error message
    :return: value corresponding to key
    """
    if key in dictionary:
        return dictionary[key]
    dict_name = "dictionary" if dict_name is None else dict_name
    raise Exception('{k} not found in {d}'.format(k=repr(key), d=dict_name))