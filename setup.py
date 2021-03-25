from setuptools import setup

setup(
    name='d43-catalog',
    version='0.0.1',
    package_dir={'acceptance-test': 'functions/acceptance',
                 'catalog': 'functions/catalog',
                 'uw-v2-catalog': 'functions/uw_v2_catalog',
                 'ts-v2-catalog': 'functions/ts_v2_catalog',
                 'signing': 'functions/signing',
                 'webhook': 'functions/webhook',
                 'status': 'functions/status',
                 'fork': 'functions/fork'},
    packages=['acceptance-test', 'catalog', 'uw-v2-catalog', 'ts-v2-catalog', 'signing', 'webhook', 'fork', 'status'],
    author='unfoldingWord',
    author_email='unfoldingword.org',
    description='Publishing door43-catalog organization.',
    license='MIT',
    keywords='',
    url='https://github.org/unfoldingWord-dev/d43-catalog',
    long_description='Publishing door43-catalog organization.',
    classifiers=[],
    install_requires=[
        'arrow==0.10.0',
        'mutagen==1.38',
        'markdown==2.6.8',
        'pyyaml==5.4',
        'gitea_client==1.0.9',
        'future==0.16.0',
        'usfm-tools==0.0.13',
        'd43_aws_tools==1.0.4',
        'boto3==1.4.4',
        'python-dateutil==2.6.0',
        'pytz==2017.2',
        'grequests==0.3.0',
        'resource_container==1.1'
    ]
)
