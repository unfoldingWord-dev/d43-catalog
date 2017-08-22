from setuptools import setup

setup(
    name="d43-catalog",
    version="0.0.1",
    author="unfoldingWord",
    author_email="unfoldingword.org",
    description="Unit test setup file.",
    license="MIT",
    keywords="",
    url="https://github.org/unfoldingWord-dev/d43-catalog",
    long_description='Unit test setup file',
    classifiers=[],
    install_requires=[
        'arrow==0.10.0',
        'mutagen==1.38',
        'coveralls==1.1',
        'markdown==2.6.8',
        'pyyaml==3.12',
        'gogs_client==1.0.6',
        'usfm-tools==0.0.12',
        'd43_aws_tools==1.0.4',
        'boto3==1.4.4',
        'python-dateutil==2.6.0',
        'pytz==2017.2',
        'grequests==0.3.0',
        'mock'  # travis reports syntax error in mock setup.cfg if we give version
    ],
    test_suite='tests'
)
