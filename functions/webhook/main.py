# -*- coding: utf-8 -*-

#
# Webhook client for updating the catalog
#

from __future__ import print_function

import os
import sys
import json
import tempfile
import requests

from datetime import datetime
from general_tools.file_utils import unzip, get_subdirs, write_file, add_contents_to_zip, add_file_to_zip
from general_tools.url_utils import download_file
from door43_tools import preprocessors
from door43_tools.manifest_handler import Manifest, MetaData
from aws_tools.s3_handler import S3Handler


def get_manifest(commit_url):
    repo_zip_url = commit_url.replace('commit', 'archive') + '.zip'
    repo_zip_file = os.path.join(tempfile.gettempdir(), repo_zip_url.rpartition('/')[2])
    try:
        print('Downloading {0}...'.format(repo_zip_url))
        if not os.path.isfile(repo_zip_file):
            download_file(repo_zip_url, repo_zip_file)
    finally:
        print('finished.')

    try:
        print('Unzipping {0}...'.format(repo_zip_file))
        unzip(repo_zip_file, repo_dir)
    finally:
        print('finished.')


def handle(event, context):
    try:
        # Get vars and data
        env_vars = retrieve(event, 'vars', 'payload')
        api_url = retrieve(env_vars, 'api_url', 'Environment Vars')
        cdn_bucket = retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        gogs_url = retrieve(env_vars, 'gogs_url', 'Environment Vars')
        gogs_user_token = retrieve(env_vars, 'gogs_user_token', 'Environment Vars')
        repo_commit = retrieve(event, 'data', 'payload')

        commit_id = repo_commit['after']
        commit = None
        for commit in repo_commit['commits']:
            if commit['id'] == commit_id:
                break
        commit_id = commit_id[:10]  # Only use the short form

        commit_url = commit['url']

        repo_name = repo_commit['repository']['name']
        repo_owner = repo_commit['repository']['owner']['username']
        compare_url = repo_commit['compare_url']

        if repo_owner != 'Door43':
            return

        if 'pusher' in repo_commit:
            pusher = repo_commit['pusher']
        else:
            pusher = {'username': commit['author']['username']}
        pusher_username = pusher['username']

        # 1) Download and unzip the repo files
        manifest = get_manifest(commit_url)

        # 2) Get the manifest file or make one if it doesn't exist based on meta.json, repo_name and file extensions
        manifest_path = os.path.join(repo_dir, 'manifest.json')
        if not os.path.isfile(manifest_path):
            manifest_path = os.path.join(repo_dir, 'project.json')
            if not os.path.isfile(manifest_path):
                manifest_path = None
        meta_path = os.path.join(repo_dir, 'meta.json')
        meta = None
        if os.path.isfile(meta_path):
            meta = MetaData(meta_path)
        manifest = Manifest(file_name=manifest_path, repo_name=repo_name, files_path=repo_dir, meta=meta)

        # determining the repo compiler:
        generator = ''
        if manifest.generator and manifest.generator['name'] and manifest.generator['name'].startswith('ts'):
            generator = 'ts'
        if not generator:
            dirs = sorted(get_subdirs(repo_dir, True))
            if 'content' in dirs:
                repo_dir = os.path.join(repo_dir, 'content')
            elif 'usfm' in dirs:
                repo_dir = os.path.join(repo_dir, 'usfm')

        manifest_path = os.path.join(repo_dir, 'manifest.json')
        write_file(manifest_path, manifest.__dict__)  # Write it back out so it's using the latest manifest format

        input_format = manifest.format
        resource_type = manifest.resource['id']
        if resource_type == 'ulb' or resource_type == 'udb':
            resource_type = 'bible'

        print(generator)
        print(input_format)
        print(manifest.__dict__)
        try:
            compiler_class = str_to_class('preprocessors.{0}{1}{2}Preprocessor'.format(generator.capitalize(),
                                                                                       resource_type.capitalize(),
                                                                                       input_format.capitalize()))
        except AttributeError as e:
            print('Got AE: {0}'.format(e.message))
            compiler_class = preprocessors.Preprocessor

        print(compiler_class)

        # merge the source files with the template
        output_dir = tempfile.mkdtemp(prefix='output_')
        compiler = compiler_class(manifest, repo_dir, output_dir)
        compiler.run()

        # 3) Zip up the massaged files
        zip_filename = context.aws_request_id + '.zip'  # context.aws_request_id is a unique ID for this lambda call, so using it to not conflict with other requests
        zip_filepath = os.path.join(tempfile.gettempdir(), zip_filename)
        print('Zipping files from {0} to {1}...'.format(output_dir, zip_filepath))
        add_contents_to_zip(zip_filepath, output_dir)
        if os.path.isfile(manifest_path) and not os.path.isfile(os.path.join(output_dir, 'manifest.json')):
            add_file_to_zip(zip_filepath, manifest_path, 'manifest.json')
        print('finished.')

        # 4) Upload zipped file to the S3 bucket (you may want to do some try/catch and give an error if fails back to Gogs)
        s3_handler = S3Handler(pre_convert_bucket)
        file_key = "preconvert/" + zip_filename
        print('Uploading {0} to {1}/{2}...'.format(zip_filepath, pre_convert_bucket, file_key))
        s3_handler.upload_file(zip_filepath, file_key)
        print('finished.')

        # Send job request to tx-manager
        source_url = 'https://s3-us-west-2.amazonaws.com/{0}/{1}'.format(pre_convert_bucket,
                                                                         file_key)  # we use us-west-2 for our s3 buckets
        callback_url = api_url + '/client/callback'
        tx_manager_job_url = api_url + '/tx/job'
        identifier = "{0}/{1}/{2}".format(repo_owner, repo_name,
                                          commit_id)  # The way to know which repo/commit goes to this job request
        if input_format == 'markdown':
            input_format = 'md'
        payload = {
            "identifier": identifier,
            "user_token": gogs_user_token,
            "resource_type": manifest.resource['id'],
            "input_format": input_format,
            "output_format": "html",
            "source": source_url,
            "callback": callback_url
        }
        headers = {"content-type": "application/json"}

        print('Making request to tx-Manager URL {0} with payload:'.format(tx_manager_job_url))
        print(payload)
        response = requests.post(tx_manager_job_url, json=payload, headers=headers)
        print('finished.')

        # for testing
        print('tx-manager response:')
        print(response)
        print(response.status_code)

        # Fake job in case tx-manager returns an error, can still build the build_log.json
        job = {
            'job_id': None,
            'identifier': identifier,
            'resource_type': manifest.resource['id'],
            'input_format': input_format,
            'output_format': 'html',
            'source': source_url,
            'callback': callback_url,
            'message': 'Conversion started...',
            'status': 'requested',
            'success': None,
            'created_at': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'log': [],
            'warnings': [],
            'errors': []
        }

        if response.status_code != requests.codes.ok:
            job['status'] = 'failed'
            job['success'] = False
            job['message'] = 'Failed to convert!'
            error = ''
            if response.text:
                try:
                    json_data = json.loads(response.text)
                    if 'errorMessage' in json_data:
                        error = json_data['errorMessage']
                        if error.startswith('Bad Request: '):
                            error = error[len('Bad Request: '):]
                except Exception:
                    pass
            job['errors'].append(error)
        else:
            json_data = json.loads(response.text)

            if 'job' not in json_data:
                job['status'] = 'failed'
                job['success'] = False
                job['message'] = 'Failed to convert'
                job['errors'].append('tX Manager did not return any info about the job request.')
            else:
                job = json_data['job']

        cdn_handler = S3Handler(cdn_bucket)

        # Download the project.json file for this repo (create it if doesn't exist) and update it
        project_json_key = 'u/{0}/{1}/project.json'.format(repo_owner, repo_name)
        project_json = cdn_handler.get_json(project_json_key)
        project_json['user'] = repo_owner
        project_json['repo'] = repo_name
        project_json['repo_url'] = 'https://git.door43.org/{0}/{1}'.format(repo_owner, repo_name)
        commit = {
            'id': commit_id,
            'created_at': job['created_at'],
            'status': job['status'],
            'success': job['success'],
            'started_at': None,
            'ended_at': None
        }
        if 'commits' not in project_json:
            project_json['commits'] = []
        commits = []
        for c in project_json['commits']:
            if c['id'] != commit_id:
                commits.append(c)
        commits.append(commit)
        project_json['commits'] = commits
        project_file = os.path.join(tempfile.gettempdir(), 'project.json')
        write_file(project_file, project_json)
        cdn_handler.upload_file(project_file, project_json_key, 0)

        # Compile data for build_log.json
        build_log_json = job
        build_log_json['repo_name'] = repo_name
        build_log_json['repo_owner'] = repo_owner
        build_log_json['commit_id'] = commit_id
        build_log_json['committed_by'] = pusher_username
        build_log_json['commit_url'] = commit_url
        build_log_json['compare_url'] = compare_url
        build_log_json['commit_message'] = commit_message
        # Upload build_log.json and manifest.json to S3:
        s3_commit_key = 'u/{0}'.format(identifier)
        for obj in cdn_handler.get_objects(prefix=s3_commit_key):
            cdn_handler.delete_file(obj.key)
        build_log_file = os.path.join(tempfile.gettempdir(), 'build_log.json')
        write_file(build_log_file, build_log_json)
        cdn_handler.upload_file(build_log_file, s3_commit_key + '/build_log.json', 0)

        cdn_handler.upload_file(manifest_path, s3_commit_key + '/manifest.json', 0)

        if len(job['errors']) > 0:
            raise Exception('; '.join(job['errors']))
        else:
            return build_log_json
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))


def retrieve(dictionary, key, dict_name=None):
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
