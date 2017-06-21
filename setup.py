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
                 'fork': 'functions/fork'},
    packages=['acceptance-test', 'catalog', 'uw-v2-catalog', 'ts-v2-catalog', 'signing', 'webhook', 'fork'],
    author='unfoldingWord',
    author_email='unfoldingword.org',
    description='Publishing door43-catalog organization.',
    license='MIT',
    keywords='',
    url='https://github.org/unfoldingWord-dev/d43-catalog',
    long_description='Publishing door43-catalog organization.',
    classifiers=[],
    install_requires=[
        'requests==2.13.0',
        'markdown==2.6.8'
        'pyyaml==3.12',
        'gogs_client==1.0.5',
        'usfm-tools==0.0.12',
        'd43_aws_tools==1.0.1'
    ]
)
