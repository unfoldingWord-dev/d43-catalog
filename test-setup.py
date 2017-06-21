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
        'coveralls==1.1',
        'requests==2.13.0',
        'markdown==2.6.8'
        'pyyaml==3.12',
        'gogs_client==1.0.5',
        'usfm-tools==0.0.12',
        'd43_aws_tools==1.0.1'
    ],
    test_suite='tests'
)
