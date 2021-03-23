# -*- coding: utf-8 -*-

#
# Class to process a Catalog repo and add it to the d43-catalog-in-progress table
#
# Updated March 2021 by RJH to handle TQ and (prepare to handle) TN backporting
#

from __future__ import print_function

# Disabled by RJH because the following import fails due to attrs/convert problem
# import gitea_client as GiteaClient
import codecs
import json
import logging
import os
import shutil
import tempfile
import arrow
import sys
import yaml
import copy
import re

from glob import glob
from d43_aws_tools import DynamoDBHandler, S3Handler
from libraries.tools.consistency_checker import ConsistencyChecker
from libraries.tools.date_utils import str_to_timestamp
from libraries.tools.file_utils import unzip, read_file, write_file
from libraries.tools.url_utils import get_url, download_file, url_exists
from libraries.tools.media_utils import parse_media

from libraries.lambda_handlers.handler import Handler


BBB_LIST = ('GEN','EXO','LEV','NUM','DEU',
        'JOS','JDG','RUT','1SA','2SA','1KI',
        '2KI','1CH','2CH','EZR', 'NEH', 'EST',
        'JOB','PSA','PRO','ECC','SNG','ISA',
        'JER','LAM','EZK','DAN','HOS','JOL',
        'AMO','OBA','JON','MIC','NAM','HAB',
        'ZEP','HAG','ZEC','MAL',
        'MAT','MRK','LUK','JHN','ACT',
        'ROM','1CO','2CO','GAL','EPH','PHP',
        'COL','1TH','2TH','1TI','2TI','TIT',
        'PHM','HEB', 'JAS','1PE','2PE',
        '1JN','2JN','3JN', 'JUD', 'REV')
assert len(BBB_LIST) == 66


current_BCV = None
markdown_text = ''

class WebhookHandler(Handler):
    def __init__(self, event, context, logger, **kwargs):
        super(WebhookHandler, self).__init__(event, context)

        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.gogs_url = self.retrieve(env_vars, 'gogs_url', 'Environment Vars')
        self.gogs_token = self.retrieve(env_vars, 'gogs_token', 'Environment Vars')
        self.gogs_org = self.retrieve(env_vars, 'gogs_org', 'Environment Vars')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')
        self.from_email = self.retrieve(env_vars, 'from_email', 'Environment Vars')
        self.to_email = self.retrieve(env_vars, 'to_email', 'Environment Vars')
        self.api_url = self.retrieve(env_vars, 'api_url', 'Environment Vars')
        self.repo_commit = self.retrieve(event, 'body-json', 'payload')
        self.api_version = self.retrieve(env_vars, 'version')

        # NOTE: it would be better to use the header X-GitHub-Event to determine the type of event.

        if 'pull_request' in self.repo_commit:
            # TODO: this is deprecated
            self.__parse_pull_request(self.repo_commit)
        # Disabled by RJH because no working Gitea support
        # elif 'forkee' in self.repo_commit or ('action' in self.repo_commit and self.repo_commit['action'] == 'created'):
        #     # handles fork and create events
        #     self.__parse_fork(self.repo_commit)
        elif 'pusher' in self.repo_commit:
            self.__parse_push(self.repo_commit)
        else:
            raise Exception('Unsupported webhook request received ' + self.repo_commit['repository']['name'] + ' ' + json.dumps(self.repo_commit))

        self.resource_id = None # set in self._build
        self.logger = logger # type: logging._loggerClass

        if 'dynamodb_handler' in kwargs:
            self.db_handler = kwargs['dynamodb_handler']
        else:
            self.db_handler = DynamoDBHandler('{}d43-catalog-in-progress'.format(self.stage_prefix())) # pragma: no cover

        if 's3_handler' in kwargs:
            self.s3_handler = kwargs['s3_handler']
        else:
            self.s3_handler = S3Handler(self.cdn_bucket) # pragma: no cover

        if 'download_handler' in kwargs:
            self.download_file = kwargs['download_handler']
        else:
            self.download_file = download_file # pragma: no cover

    def __parse_pull_request(self, payload):
        """
        Parses a  pull request
        :param payload:
        :return: True if the pull request should be processed
        """

        pull_request = self.retrieve(payload, 'pull_request', 'payload')

        self.repo_owner = payload['repository']['owner']['username']
        self.repo_name = payload['repository']['name']
        self.temp_repo_dir_path = tempfile.mkdtemp('', self.repo_name, None)
        self.temp_repo_zipfile_path = os.path.join(self.temp_repo_dir_path, self.repo_name + '.zip')
        # TRICKY: gogs gives a lower case name to the folder in the zip archive
        self.repo_dir_path = os.path.join(self.temp_repo_dir_path, self.repo_name.lower())

        commit_sha = self.retrieve(pull_request, 'merge_commit_sha', 'pull_request')
        self.timestamp = str_to_timestamp(self.retrieve(pull_request, 'merged_at', 'pull_request'))
        repository = self.retrieve(payload, 'repository', 'payload')
        url = self.retrieve(repository, 'html_url', 'repository').rstrip('/')
        self.commit_url = '{}/commit/{}'.format(url, commit_sha)
        if commit_sha:
            self.commit_id = commit_sha[:10]
        else:
            self.commit_id = None

    # Disabled by RJH because no working Gitea support
    # def __parse_fork(self, payload):
    #     """
    #     Parses a forked repository webhook
    #     :param payload:
    #     :return:
    #     """
    #     self.repo_owner = payload['repository']['owner']['username']
    #     self.repo_name = payload['repository']['name']
    #     default_branch = payload['repository']['default_branch']
    #     self.temp_repo_dir_path = tempfile.mkdtemp('', self.repo_name, None)
    #     self.temp_repo_zipfile_path = os.path.join(self.temp_repo_dir_path, self.repo_name + '.zip')
    #     # TRICKY: gogs gives a lower case name to the folder in the zip archive
    #     self.repo_dir_path = os.path.join(self.temp_repo_dir_path, self.repo_name.lower())

    #     # fetch latest commit from DCS
    #     gogs_client = GiteaClient
    #     gogs_api = gogs_client.GiteaApi(self.gogs_url)
    #     gogs_auth = gogs_client.Token(self.gogs_token)
    #     branch = gogs_api.get_branch(gogs_auth, self.gogs_org, self.repo_name, default_branch)

    #     self.commit_url = branch.commit.url
    #     self.commit_id = branch.commit.id
    #     self.timestamp = branch.commit.timestamp
    #     self.commit_id = self.commit_id[:10]

    #     # self.commit_id = payload['after']
    #     # commit = None
    #     # for commit in payload['commits']:
    #     #     if commit['id'] == self.commit_id:
    #     #         break
    #     # self.commit_url = commit['url']
    #     # self.timestamp = str_to_timestamp(commit['timestamp'])
    #     # self.commit_id = self.commit_id[:10]

    def __parse_push(self, payload):
        """
        Parses a regular push commit
        :param payload:
        :return:
        """
        self.repo_owner = payload['repository']['owner']['username']
        self.repo_name = payload['repository']['name']
        self.temp_repo_dir_path = tempfile.mkdtemp('', self.repo_name, None)
        self.temp_repo_zipfile_path = os.path.join(self.temp_repo_dir_path, self.repo_name + '.zip')
        # TRICKY: gogs gives a lower case name to the folder in the zip archive
        self.repo_dir_path = os.path.join(self.temp_repo_dir_path, self.repo_name.lower())

        self.commit_id = payload['after']
        commit = None
        for commit in payload['commits']:
            if commit['id'] == self.commit_id:
                break
        self.commit_url = commit['url']
        self.timestamp = str_to_timestamp(commit['timestamp'])
        self.commit_id = self.commit_id[:10] # Only use the short version of the commit hash

    def _run(self):
        if not self.commit_url.startswith(self.gogs_url):
            raise Exception('Only accepting webhooks from {0} but found {1}'.format(self.gogs_url, self.commit_url)) # pragma: no cover

        if self.repo_owner.lower() != self.gogs_org.lower():
            raise Exception("Only accepting repos from the {0} organization".format(self.gogs_org)) # pragma: no cover

        # skip un-merged pull requests
        if 'pull_request' in self.repo_commit:
            pr = self.repo_commit['pull_request']
            if not pr['merged']:
                raise Exception('Webhook handler skipping un-merged pull request ' + self.repo_name)

        try:
            # build catalog entry
            data = self._build()
            if data:
                # upload data
                if 'uploads' in data:
                    self.logger.debug('Uploading files for "{}"'.format(self.repo_name))
                    for upload in data['uploads']:
                        self.logger.debug('^…{}'.format(upload['key']))
                        self.s3_handler.upload_file(upload['path'], upload['key'])
                    del data['uploads']
                else:
                    self.logger.debug('No upload-able content found in "{}"'.format(self.repo_name))
                self.db_handler.insert_item(data)
            else:
                self.logger.debug('No data found in {}'.format(self.repo_name))
        except Exception as e:
            self.report_error(e.message)
            raise Exception, Exception(e), sys.exc_info()[2]
        finally:
            # clean
            if self.temp_repo_dir_path and os.path.isdir(self.temp_repo_dir_path):
                shutil.rmtree(self.temp_repo_dir_path, ignore_errors=True)

        return {
            "success": True,
            "message": "Successfully added {0} ({1}) to the catalog".format(self.repo_name, self.commit_id)
        }

    def _build(self):
        """
        Constructs a new catalog entry from the repository
        :return: the constructed object
        """

        self.download_repo(self.commit_url, self.temp_repo_zipfile_path)
        self.unzip_temp_repo_zipfile_path(self.temp_repo_zipfile_path, self.temp_repo_dir_path)

        if not os.path.isdir(self.repo_dir_path):
            raise Exception('Was not able to find {0}'.format(self.repo_dir_path)) # pragma: no cover

        self.logger.info('Webhook handler processing repository "{}"'.format(self.repo_name))
        data = {}
        if self.repo_name == 'localization':
            data = self._build_localization()
        elif self.repo_name == 'catalogs':
            data = self._build_catalogs()
        elif self.repo_name == 'versification':
            # TODO: we do not yet know what to do with versification
            return None
        else:
            # Here's where we catch repos which we need to backport new TSV versions to the expected v3 Catalog formats
            initial_manifest = self._get_initial_manifest_data()
            if (self.repo_name.endswith('_tq') or self.repo_name.endswith('-tq') or self.repo_name == 'en_tq-tsv-test') \
            and initial_manifest['dublin_core']['format'] == 'text/tsv':
                data = self._tq_tsv_backport_build_rc(initial_manifest)
            elif (self.repo_name.endswith('_tn') or self.repo_name.endswith('-tn')) \
            and initial_manifest['dublin_core']['format'] == 'text/tsv':
                data = self._tn_tsv_backport_build_rc(initial_manifest)
            else:
                data = self._default_build_rc(initial_manifest)

        return data

    def _get_initial_manifest_data(self):
        """
        Read the manifest and sanitize some of the data
        """
        manifest_path = os.path.join(self.repo_dir_path, 'manifest.yaml')
        if not os.path.isfile(manifest_path):
            raise Exception('Repository {0} does not have a manifest.yaml file'.format(self.repo_name))
        try:
            manifest = WebhookHandler.load_yaml_file(manifest_path)
        except Exception as e:
            raise Exception('Bad Manifest: {0}'.format(e))

        try:
            ConsistencyChecker.check_manifest(manifest)
        except Exception as e:
            raise Exception('Bad Manifest: {0}'.format(e))

        # identifiers must be lowercase
        manifest['dublin_core']['identifier'] = self.sanitize_identifier(manifest['dublin_core']['identifier'])
        # resource version must be string
        manifest['dublin_core']['version'] = '{}'.format(manifest['dublin_core']['version'])

        # normalize dates
        try:
            manifest['dublin_core']['modified'] = str_to_timestamp(manifest['dublin_core']['modified'])
        except Exception as e:
            self.logger.warning('Invalid datetime detected: {}'.format(e.message))
        try:
            manifest['dublin_core']['issued'] = str_to_timestamp(manifest['dublin_core']['issued'])
        except Exception as e:
            self.logger.warning('Invalid datetime detected: {}'.format(e.message))

        return manifest

    def _tq_tsv_backport_build_rc(self, manifest):
        """
        Builds a backported TQ markdown Resource Container following the RC0.2 spec
        :return:
        """
        self.logger.debug("In '{0}' _tq_tsv_backport_build_rc with initial manifest: {1}".format(self.stage_prefix(), manifest['dublin_core']))

        # build media formats
        media_path = os.path.join(self.repo_dir_path, 'media.yaml')
        resource_formats = []
        project_formats = {}
        if os.path.isfile(media_path):
            try:
                media = WebhookHandler.load_yaml_file(media_path)
            except Exception as e:
                raise Exception('Bad Media: {0}'.format(e))
            project_chapters = self._listChapters(self.repo_dir_path, manifest)
            try:
                resource_formats, project_formats = parse_media(media=media,
                            content_version=manifest['dublin_core']['version'],
                            project_chapters=project_chapters)
            except Exception as e:
                self.report_error('Failed to parse media in {}. {}'.format(self.repo_name, e.message))
        self.logger.debug("resource_formats={}".format(resource_formats))
        self.logger.debug("project_formats={}".format(project_formats))

        # Convert TQ TSV to markdown files and folders
        # The following code is adapted from https://github.com/unfoldingWord-dev/tools/blob/develop/tsv/TQ_TSV7_to_MD.py (Python3)
        def get_TSV_fields(input_folderpath, BBB):
            """
            Generator to read the TQ 5-column TSV file for a given book (BBB)
                and return the needed fields.

            Skips the heading row.
            Checks that unused fields are actually unused.

            Returns a 3-tuple with:
                reference, question, response
            """
            self.logger.debug("Loading TQ {} links from 7-column TSV…".format(BBB))
            input_filepath = os.path.join(input_folderpath,'tq_{}.tsv'.format(BBB))
            with open(input_filepath, 'rt') as input_TSV_file:
                for line_number, line in enumerate(input_TSV_file, start=1):
                    line = line.rstrip('\n\r')
                    # self.logger.debug("{:3}/ {}".format(line_number,line))
                    if line_number == 1:
                        if line != 'Reference\tID\tTags\tQuote\tOccurrence\tQuestion\tResponse':
                            self.report_error('Unexpected TSV header {!r} in {}'.format(line, input_filepath))
                    else:
                        reference, rowID, tags, quote, occurrence, question, response = line.split('\t')
                        assert reference; assert rowID; assert question; assert response
                        assert not tags; assert not quote; assert not occurrence
                        yield reference, question, response
        # end of get_TSV_fields function

        def handle_output(output_folderpath, BBB, fields):
            """
            Function to write the TQ markdown files.

            Needs to be called one extra time with fields = None
                to write the last entry.

            Returns the number of markdown files that were written in the call.
            """
            global current_BCV, markdown_text
            num_files_written = 0

            if fields is not None:
                reference, question, response = fields
                C, V = reference.split(':')
                # self.logger.debug(BBB,C,V,repr(annotation))

            if (fields is None # We need to write the last file
            or (markdown_text and (BBB,C,V) != current_BCV)): # need to write the previous verse file
                assert BBB == current_BCV[0]
                prevC, prevV = current_BCV[1:]
                this_folderpath = os.path.join(output_folderpath, '{}/{}/'.format(BBB.lower(),prevC.zfill(2)))
                if not os.path.exists(this_folderpath): os.makedirs(this_folderpath)
                output_filepath = os.path.join(output_folderpath,'{}/{}.md'.format(this_folderpath,prevV.zfill(2)))
                with open(output_filepath, 'wt') as output_markdown_file:
                    output_markdown_file.write(markdown_text)
                num_files_written += 1
                markdown_text = ''

            if fields is not None:
                current_BCV = BBB, C, V
                # question, answer = annotation.split('\\n\\n> ')
                if markdown_text: markdown_text += '\n' # Blank line between questions
                markdown_text += '# {}\n\n{}\n'.format(question,response) # will be written on the next call

            return num_files_written
        # end of handle_output function

        # Convert TSV files to markdown
        tsv_source_folderpath = self.repo_dir_path
        md_output_folderpath = os.path.join(self.temp_repo_dir_path,'outputFolder/')
        os.mkdir(md_output_folderpath)
        self.logger.debug("Source folderpath is {}/".format(tsv_source_folderpath))
        self.logger.debug("Source contents are {}/".format(os.listdir(tsv_source_folderpath)))
        self.logger.debug("Output folderpath is {}/".format(md_output_folderpath))
        total_files_read = total_questions = total_files_written = 0
        for BBB in BBB_LIST:
            for input_fields in get_TSV_fields(tsv_source_folderpath,BBB):
                total_files_written += handle_output(md_output_folderpath,BBB,input_fields)
                total_questions += 1
            total_files_read += 1
            total_files_written += handle_output(md_output_folderpath,BBB,None) # To write last file
        self.logger.debug("{:,} total questions and answers read from {} TSV files".format(total_questions,total_files_read))
        self.logger.debug("{:,} total verse files written to {}/".format(total_files_written,md_output_folderpath))

        # Copy across manifest, LICENSE, README to the new markdown folder
        shutil.copy(os.path.join(tsv_source_folderpath,'manifest.yaml'), md_output_folderpath)
        shutil.copy(os.path.join(tsv_source_folderpath,'README.md'), md_output_folderpath)
        shutil.copy(os.path.join(tsv_source_folderpath,'LICENSE.md'), md_output_folderpath)
        self.logger.debug("Output contents are {}/".format(os.listdir(md_output_folderpath)))

        # Now, switch folders to fool the rest of the system
        self.repo_dir_path = md_output_folderpath # This self variable might not actually be used anymore anyway?

        # TODO here: zip the above folder and substitute that

        # TRICKY: single-project RCs get named after the project to avoid conflicts with multi-project RCs.
        if len(manifest['projects']) == 1:
            zip_name = manifest['projects'][0]['identifier'].lower()
        else:
            zip_name = manifest['dublin_core']['identifier']

        resource_key = '{}/{}/v{}/{}.zip'.format(
                                                manifest['dublin_core']['language']['identifier'],
                                                manifest['dublin_core']['identifier'].split('-')[-1],
                                                manifest['dublin_core']['version'],
                                                zip_name)
        url = '{}/{}'.format(self.cdn_url, resource_key)
        self.logger.debug("zn='{}' rk='{}' url='{}'".format(zip_name, resource_key, url))

        stats = os.stat(self.temp_repo_zipfile_path)
        file_info = {
            'size': stats.st_size,
            'modified': self.timestamp,
            'format': 'application/zip; type={0} content={1} conformsto={2}'.format(manifest['dublin_core']['type'],
                                                                                    manifest['dublin_core'][
                                                                                        'format'],
                                                                                    manifest['dublin_core'][
                                                                                        'conformsto']),
            'url': url,
            'signature': ""
        }
        manifest['formats'] = [file_info]

        uploads = [{
                'key': self.make_upload_key(resource_key),
                'path': self.temp_repo_zipfile_path
            }]
        self.logger.debug("fi='{}' upl='{}'".format(file_info, uploads))

        # add media to projects
        for project in manifest['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            if pid in project_formats:
                if 'formats' not in project: project['formats'] = []
                project['formats'] = project['formats'] + project_formats[pid]
            self.logger.debug("pid={} project['formats']={}",format(pid, project['formats']))

        # add media to resource
        manifest['formats'] = manifest['formats'] + resource_formats
        self.logger.debug("manifest['formats']={}",format(manifest['formats']))

        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'language': manifest['dublin_core']['language']['identifier'],
            'timestamp': self.timestamp,
            'added_at': arrow.utcnow().isoformat(),
            'package': json.dumps(manifest, sort_keys=True),
            'signed': False,
            'dirty': False,
            'uploads': uploads
        }

    def _tn_tsv_backport_build_rc(self, manifest):
        """
        Builds a backported TN Resource Container following the RC0.2 spec
        :return:
        """
        self.logger.debug("In '{0}' _tn_tsv_backport_build_rc with initial manifest: {1}".format(self.stage_prefix(), manifest['dublin_core']))

        # build media formats
        media_path = os.path.join(self.repo_dir_path, 'media.yaml')
        resource_formats = []
        project_formats = {}
        if os.path.isfile(media_path):
            try:
                media = WebhookHandler.load_yaml_file(media_path)
            except Exception as e:
                raise Exception('Bad Media: {0}'.format(e))
            project_chapters = self._listChapters(self.repo_dir_path, manifest)
            try:
                resource_formats, project_formats = parse_media(media=media,
                            content_version=manifest['dublin_core']['version'],
                            project_chapters=project_chapters)
            except Exception as e:
                self.report_error('Failed to parse media in {}. {}'.format(self.repo_name, e.message))
        self.logger.debug("resource_formats={}".format(resource_formats))
        self.logger.debug("project_formats={}".format(project_formats))

        stats = os.stat(self.temp_repo_zipfile_path)

        # TRICKY: single-project RCs get named after the project to avoid conflicts with multi-project RCs.
        if len(manifest['projects']) == 1:
            zip_name = manifest['projects'][0]['identifier'].lower()
        else:
            zip_name = manifest['dublin_core']['identifier']

        resource_key = '{}/{}/v{}/{}.zip'.format(
                                                manifest['dublin_core']['language']['identifier'],
                                                manifest['dublin_core']['identifier'].split('-')[-1],
                                                manifest['dublin_core']['version'],
                                                zip_name)
        url = '{}/{}'.format(self.cdn_url, resource_key)
        self.logger.debug("zn='{}' rk='{}' url='{}'".format(zip_name, resource_key, url))

        file_info = {
            'size': stats.st_size,
            'modified': self.timestamp,
            'format': 'application/zip; type={0} content={1} conformsto={2}'.format(manifest['dublin_core']['type'],
                                                                                    manifest['dublin_core'][
                                                                                        'format'],
                                                                                    manifest['dublin_core'][
                                                                                        'conformsto']),
            'url': url,
            'signature': ""
        }
        manifest['formats'] = [file_info]

        uploads = [{
                'key': self.make_upload_key(resource_key),
                'path': self.temp_repo_zipfile_path
            }]
        self.logger.debug("fi='{}' upl='{}'".format(file_info, uploads))

        # add media to projects
        for project in manifest['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            if pid in project_formats:
                if 'formats' not in project: project['formats'] = []
                project['formats'] = project['formats'] + project_formats[pid]
            self.logger.debug("pid={} project['formats']={}",format(pid, project['formats']))

        # add media to resource
        manifest['formats'] = manifest['formats'] + resource_formats
        self.logger.debug("manifest['formats']={}",format(manifest['formats']))

        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'language': manifest['dublin_core']['language']['identifier'],
            'timestamp': self.timestamp,
            'added_at': arrow.utcnow().isoformat(),
            'package': json.dumps(manifest, sort_keys=True),
            'signed': False,
            'dirty': False,
            'uploads': uploads
        }

    def _default_build_rc(self, manifest):
        """
        Builds a Resource Container following the RC0.2 spec
        :return:
        """
        # self.logger.debug("In '{0}' _default_build_rc with initial manifest: {1}".format(self.stage_prefix(), manifest['dublin_core']))

        # build media formats
        media_path = os.path.join(self.repo_dir_path, 'media.yaml')
        resource_formats = []
        project_formats = {}
        if os.path.isfile(media_path):
            try:
                media = WebhookHandler.load_yaml_file(media_path)
            except Exception as e:
                raise Exception('Bad Media: {0}'.format(e))
            project_chapters = self._listChapters(self.repo_dir_path, manifest)
            try:
                resource_formats, project_formats = parse_media(media=media,
                            content_version=manifest['dublin_core']['version'],
                            project_chapters=project_chapters)
            except Exception as e:
                self.report_error('Failed to parse media in {}. {}'.format(self.repo_name, e.message))

        stats = os.stat(self.temp_repo_zipfile_path)

        # TRICKY: single-project RCs get named after the project to avoid conflicts with multi-project RCs.
        if len(manifest['projects']) == 1:
            zip_name = manifest['projects'][0]['identifier'].lower()
        else:
            zip_name = manifest['dublin_core']['identifier']

        resource_key = '{}/{}/v{}/{}.zip'.format(
                                                manifest['dublin_core']['language']['identifier'],
                                                manifest['dublin_core']['identifier'].split('-')[-1],
                                                manifest['dublin_core']['version'],
                                                zip_name)
        url = '{}/{}'.format(self.cdn_url, resource_key)

        file_info = {
            'size': stats.st_size,
            'modified': self.timestamp,
            'format': 'application/zip; type={0} content={1} conformsto={2}'.format(manifest['dublin_core']['type'],
                                                                                    manifest['dublin_core'][
                                                                                        'format'],
                                                                                    manifest['dublin_core'][
                                                                                        'conformsto']),
            'url': url,
            'signature': ""
        }
        manifest['formats'] = [file_info]

        uploads = [{
                'key': self.make_upload_key(resource_key),
                'path': self.temp_repo_zipfile_path
            }]

        # split usfm bundles
        if manifest['dublin_core']['type'] == 'bundle' and manifest['dublin_core']['format'] == 'text/usfm':
            for project in manifest['projects']:
                pid = self.sanitize_identifier(project['identifier'])
                if 'formats' not in project:
                    project['formats'] = []
                resource_id = manifest['dublin_core']['identifier'].split('-')[-1]
                project_key = '{}/{}/v{}/{}.usfm'.format(
                                                        manifest['dublin_core']['language']['identifier'],
                                                        resource_id,
                                                        manifest['dublin_core']['version'],
                                                        pid)
                project_url = '{}/{}'.format(self.cdn_url, project_key)
                p_file_path = os.path.join(self.repo_dir_path, project['path'].lstrip('\.\/'))
                p_stats = os.stat(p_file_path)
                try:
                    resource_mtime = str_to_timestamp(manifest['dublin_core']['modified'])
                except Exception as e:
                    self.logger.warning('Invalid datetime detected: {}'.format(e.message))
                    resource_mtime = manifest['dublin_core']['modified']
                project['formats'].append({
                    'format': 'text/usfm',
                    'modified': resource_mtime,
                    'signature': '',
                    'size': p_stats.st_size,
                    'url': project_url
                })
                uploads.append({
                    'key': self.make_upload_key(project_key),
                    'path': p_file_path
                })

        # add media to projects
        for project in manifest['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            if pid in project_formats:
                if 'formats' not in project: project['formats'] = []
                project['formats'] = project['formats'] + project_formats[pid]

        # add media to resource
        manifest['formats'] = manifest['formats'] + resource_formats

        # add html format
        # TRICKY: these URLS are only available in prod
        # for project in manifest['projects']:
        #     pid = self.sanitize_identifier(project['identifier'])
        #     html_url = ''
        #     if manifest['dublin_core']['identifier'] == 'obs':
        #         # obs html
        #         html_url = 'https://api.door43.org/tx/print?id={}/{}/{}'.format(self.gogs_org, self.repo_name, self.commit_id)
        #     elif manifest['dublin_core']['identifier'] == 'ta':
        #         # ta html
        #         sort_slug = '{}'.format(int(project['sort']) + 1).zfill(2)
        #         html_url = 'https://cdn.door43.org/u/Door43-Catalog/{}/{}/{}-{}.html'.format(self.repo_name, self.commit_id, sort_slug, pid)
        #     elif manifest['dublin_core']['identifier'] not in ['tq', 'tn', 'tw', 'obs-tn', 'obs-tq']:
        #         # we also have html for Bible resources
        #         name, _ = os.path.splitext(os.path.basename(project['path']))
        #         html_url = 'https://cdn.door43.org/u/Door43-Catalog/{}/{}/{}.html'.format(self.repo_name, self.commit_id, name)
        #
        #     if html_url and url_exists(html_url):
        #         self.logger.info('Injecting {} html url: {}'.format(manifest['dublin_core']['identifier'], html_url))
        #         if 'formats' not in project: project['formats'] = []
        #         project['formats'].append({
        #             'format': 'text/html',
        #             'modified': '',
        #             'signature': '',
        #             'size': '',
        #             'url': html_url,
        #             'build_rules': [
        #                 'signing.html_format'
        #             ]
        #         })
        #     else:
        #         self.logger.warning('Missing html format for {}_{} at {}'.format(self.repo_name, pid, html_url))

        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'language': manifest['dublin_core']['language']['identifier'],
            'timestamp': self.timestamp,
            'added_at': arrow.utcnow().isoformat(),
            'package': json.dumps(manifest, sort_keys=True),
            'signed': False,
            'dirty': False,
            'uploads': uploads
        }


    def _listChapters(self, rc_dir, manifest):
        """
        Builds a dictionary of chapter ids for each project
        :param rc_dir:
        :param manifest:
        :return:
        """
        chapters = {}
        if manifest['dublin_core']['type'] == 'book':
            for project in manifest['projects']:
                pid = self.sanitize_identifier(project['identifier'])
                project_path = os.path.normpath(os.path.join(rc_dir, project['path']))
                if os.path.isdir(project_path):
                    files = os.listdir(project_path)
                    for chapter in files:
                        if chapter in ['.', '..', 'toc.yaml', 'config.yaml', 'back', 'front']:
                            continue
                        chapter = chapter.split('.')[0]
                        if pid not in chapters:
                            chapters[pid] = []
                        chapters[pid].append(chapter)
        else:
            id = '_'.join([manifest['dublin_core']['language']['identifier'],
                           manifest['dublin_core']['identifier'],
                           manifest['dublin_core']['type']
                           ])
            self.logger.warning('Failed to generate media chapters. Only book RCs are currently supported. {}'.format(id))
        return chapters

    def _build_versification(self):
        """
        DEPRECATED

        we are no longer processing versification.
        :return:
        """
        bible_dir = os.path.join(self.repo_dir_path, 'bible')
        versification_dirs = os.listdir(bible_dir)
        books = {}
        package = []
        uploads = []

        # group by project
        for vrs_dir in versification_dirs:
            vrs_id = os.path.basename(vrs_dir)
            book_files = sorted(glob(os.path.join(bible_dir, vrs_dir, 'chunks', '*.json')))
            for b in book_files:
                self.logger.debug('Reading "{}" versification for "{}"'.format(vrs_id, b))
                b_id = os.path.splitext(os.path.basename(b))[0]
                try:
                    book_vrs = json.loads(read_file(b))
                except Exception as e:
                    raise Exception, Exception('Bad JSON: {0}'.format(e)), sys.exc_info()[2]
                book = WebhookHandler.retrieve_or_make(books, b_id, {
                    'identifier': b_id,
                    'chunks_url': '{0}/bible/{}/{}/v{}/chunks.json'.format(self.cdn_url, vrs_id, b_id, self.api_version),
                    'chunks': {}
                })
                book['chunks'][vrs_id] = book_vrs
        temp_repo_dir_path = os.path.join(self.temp_repo_dir_path, 'versification')
        if not os.path.isdir:
            os.mkdir(temp_repo_dir_path)
        for book in books:
            book = books[book]

            # write chunks
            chunk_file = os.path.join(temp_repo_dir_path, book['identifier'] + '.json')
            write_file(chunk_file, json.dumps(book['chunks'], sort_keys=True))
            # for now we bypass signing and upload chunks directly
            upload_key = 'bible/{}/v{}/chunks.json'.format(book['identifier'], self.api_version)
            uploads.append({
                'key': upload_key,
                'path': chunk_file
            })

            # build package
            del book['chunks']
            package.append(book)

        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': json.dumps(package, sort_keys=True),
            'uploads': uploads,
            'dirty': False
        }


    def _build_localization(self):
        """
        Builds the localization for various components in the catalog
        :return:
        """
        files = sorted(glob(os.path.join(self.repo_dir_path, '*.json')))
        localization = {}
        for f in files:
            self.logger.debug("Webhook handler _build_localization reading {0}…".format(f))
            language = os.path.splitext(os.path.basename(f))[0]
            try:
                localization[language] = json.loads(read_file(f))
            except Exception as e:
                raise Exception('Bad JSON: {0}'.format(e))
        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': json.dumps(localization, sort_keys=True),
            'dirty': False
        }

    def _build_catalogs(self):
        """
        Builds the global catalogs
        :return:
        """
        catalogs_path = os.path.join(self.repo_dir_path, 'catalogs.json')
        package = read_file(catalogs_path)
        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': package,
            'dirty': False
        }

    def make_upload_key(self, path):
        """
        Generates an upload key that conforms to the format `temp/<repo_name>/<commit>/<path>`.
        This allows further processing to associate files with an entry in dynamoDB.
        :param path:
        :return:
        """
        return 'temp/{0}/{1}/{2}'.format(self.repo_name, self.commit_id, path)

    @staticmethod
    def retrieve_or_make(dictionary, key, default=None):
        """
        Retrieves a value from a dictionary.
        If the key does not exist it will be created with the default value
        :param dict dictionary:
        :param any key:
        :param default:
        :return:
        """
        if  key not in dictionary:
            dictionary[key] = default
        return dictionary[key]

    @staticmethod
    def load_yaml_file(file_name, default=None):
        """
        Deserialized <file_name> into a Python object
        :param str|unicode file_name: The name of the file to read
        :param default: The value to return if the file is not found
        """
        if not os.path.isfile(file_name):
            return default

        # use utf-8-sig in case the file has a Byte Order Mark
        with codecs.open(file_name, 'r', 'utf-8-sig') as stream:
            return yaml.load(stream)

    def get_url(self, url):
        return get_url(url)

    def download_repo(self, commit_url, temp_repo_zipfile_path):
        repo_zip_url = commit_url.replace('commit', 'archive') + '.zip'
        try:
            self.logger.debug('Webhook handler downloading {0}…'.format(repo_zip_url))
            if not os.path.isfile(temp_repo_zipfile_path):
                self.download_file(repo_zip_url, temp_repo_zipfile_path)
        finally:
            pass

    def unzip_temp_repo_zipfile_path(self, temp_repo_zipfile_path, repo_dir_path):
        try:
            self.logger.debug('Webhook handler unzipping {0}…'.format(temp_repo_zipfile_path))
            unzip(temp_repo_zipfile_path, repo_dir_path)
        finally:
            pass