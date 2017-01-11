# -*- coding: utf-8 -*-

"""
These classes are a representation of the payload received by the `handle` method in main.py.

They were created to facilitate unit testing.
"""


class GogsUser(object):
    def __init__(self):
        self.id = 0           # type: int
        self.username = ''    # type: str|unicode
        self.full_name = ''   # type: str|unicode
        self.email = ''       # type: str|unicode
        self.avatar_url = ''  # type: str|unicode


class GogsCommitter(object):
    def __init__(self):
        self.name = ''
        self.email = ''
        self.username = ''


class GogsRepository(object):
    def __init__(self):
        self.id = 0                               # type: int
        self.owner = {}                           # type: GogsUser
        self.name = ''                            # type: str|unicode
        self.full_name = ''                       # type: str|unicode
        self.description = ''                     # type: str|unicode
        self.private = False                      # type: bool
        self.fork = False                         # type: bool
        self.html_url = ''                        # type: str|unicode
        self.ssh_url = ''                         # type: str|unicode
        self.clone_url = ''                       # type: str|unicode
        self.website = ''                         # type: str|unicode
        self.stars_count = 0                      # type: int
        self.forks_count = 0                      # type: int
        self.watchers_count = 0                   # type: int
        self.open_issues_count = 0                # type: int
        self.default_branch = 'master'            # type: str|unicode
        self.created_at = '2017-01-11T07:55:37Z'  # type: str|unicode
        self.updated_at = '2017-01-11T07:55:49Z'  # type: str|unicode
        self.permissions = {'admin': False,
                            'push': False,
                            'pull': False}


class GogsCommit(object):
    def __init__(self):
        self.id = ''                             # type: str|unicode
        self.message = ''                        # type: str|unicode
        self.url = ''                            # type: str|unicode
        self.author = {}                         # type: GogsCommitter
        self.committer = {}                      # type: GogsCommitter
        self.timestamp = '2017-01-11T07:55:49Z'  # type: str|unicode


class WebhookPayload(object):
    def __init__(self):
        self.secret = ''                # type: str|unicode
        self.ref = 'refs/heads/master'  # type: str|unicode
        self.before = ''                # type: str|unicode
        self.after = ''                 # type: str|unicode
        self.compare_url = ''           # type: str|unicode
        self.commits = []               # type: list<GogsCommit>
        self.repository = {}            # type: GogsRepository
        self.pusher = {}                # type: GogsUser
        self.sender = {}                # type: GogsUser
