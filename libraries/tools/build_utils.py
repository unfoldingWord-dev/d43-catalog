def get_build_rules(obj, scope=''):
    """
    Returns a list of build rules found in the object.
    If no build rules are found an empty list is returned.
    :param obj: the object that may contain build rules.
    :param scope: limits the returned rules to those in the scope e.g. signing.sign_given_url has the scope "signing".
    :return: the found rules.
    """
    rules = []
    if obj and 'build_rules' in obj and isinstance(obj['build_rules'], list):
        if scope:
            for rule in obj['build_rules']:
                if rule.startswith('{}.'.format(scope)):
                    rules.append(rule[len('{}.'.format(scope)):])
        else:
            rules = obj['build_rules']
    return rules
