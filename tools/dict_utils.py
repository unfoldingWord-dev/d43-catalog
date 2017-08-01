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

import collections

def merge_dict(orig_dict, new_dict):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``new_dict`` is merged into
    ``orig_dict``. Lists within the dictionaries are joined.
    :param orig_dict: dict onto which the merge is executed
    :param new_dict: dct merged into dct
    :return: None
    """
    for k, v in new_dict.items():
        if (k in orig_dict and isinstance(orig_dict[k], dict)
                and isinstance(new_dict[k], collections.Mapping)):
            merge_dict(orig_dict[k], new_dict[k])
        elif (k in orig_dict and isinstance(orig_dict[k], list)
              and isinstance(new_dict[k], list)):
            orig_dict[k] = orig_dict[k] + new_dict[k]
        else:
            orig_dict[k] = new_dict[k]