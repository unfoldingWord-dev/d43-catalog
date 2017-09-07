master:
[![Build Status](https://travis-ci.org/unfoldingWord-dev/d43-catalog.svg?branch=master)](https://travis-ci.org/unfoldingWord-dev/d43-catalog) 
[![Coverage Status](https://coveralls.io/repos/github/unfoldingWord-dev/d43-catalog/badge.svg?branch=master)](https://coveralls.io/github/unfoldingWord-dev/d43-catalog?branch=master)

develop:
[![Build Status](https://travis-ci.org/unfoldingWord-dev/d43-catalog.svg?branch=develop)](https://travis-ci.org/unfoldingWord-dev/d43-catalog) 
[![Coverage Status](https://coveralls.io/repos/github/unfoldingWord-dev/d43-catalog/badge.svg?branch=develop)](https://coveralls.io/github/unfoldingWord-dev/d43-catalog?branch=develop)

# d43-catalog

These are the AWS Lambda functions for generating the [API catalog endpoint](https://api.door43.org/v3/catalog) from the [Door43 Catalog] organization in our Door43 Git Service.

## Requirements
* Python 2.7
* [API Specification](https://github.com/unfoldingWord-dev/api-index)

## How it Works

When a new repository is added or forked into the [Door43 Catalog] organization a chain reaction is started that eventually adds the content into the [API](https://api.door43.org/v3/catalog), assuming all the checks passed.  Here is an overview:

1. Someone creates a new repository or forks a repository into the [Door43 Catalog] organization
2. The organization triggers the `webhook` function which queues the latest git commit for processing.

> The next few functions run on a fixed schedule.
> If errors occur they are reported and the process resumed
> at the next scheduled run.
>
> If a function produces errors 4 times in a row an email is sent to administrators.

3. The `signing` function looks for and signs new things in the queue.
4. The `catalog` function takes everything in the queue and generates a new api catalog file. **The content is now in the API!**
5. The `ts_v2_catalog` function converts the API catalog file into the legacy translationStudio API.
6. The `uw_v2_catalog` function converts the API catalog file into the legacy unfoldingWord App Catalog.
7. The `fork` function checks to see if new repositories exist in the organization and executes the `webhook` function if necessary.

> The content in step (1) is now available in all three API endpoints.

7. The `acceptance` function runs when the catalog file is saved in step (4) above. And performs acceptance tests on the file to ensure it was generated correctly.


## Function Description

The following provides a functional description of the functions in this repository.

### webhook 

Runs when a change is made in the [Door43 Catalog]

* [x] Accept webhook from organization.
* [x] Reads manifest from the repository (via HTTPS)
* [x] Performs some initial manifest validation. See [Manifest Specification](http://resource-container.readthedocs.io/en/latest/manifest.html)
* [x] Uploads files and adds/updates an entry to the queue

### signing

This function is run on a schedule and does the following:

- [x] Identifies items in the queue that require signing.
- [x] Signs files as necessary
- [x] Verifies that signature checks out
- [x] Copies files to proper location on CDN as necessary.
- [x] Uploads the signature file to the CDN
- [x] Updates the queued item with appropriate urls and file meta data as necessary.

### catalog

This function is run on a schedule and does the following:

- [x] Performs a consistency check on queued items
- [x] Generates the new catalog file
- [x] Uploads the catalog file to the API.
- [x] Records the catalog status in the status table.
- [x] Errors or consistency failures are reported as errors.

### acceptance

After a new catalog file is written to S3, this function does the following:

- [x] Make sure structure of catalog file is correct
- [x] Make HEAD request for each resource (every URL) in catalog to verify it exists
- [x] Report any errors

Technically this is all duplicate testing of what we are already doing elsewhere in the pipeline.  This function is the "oops" catcher.

### fork

This function is run on a schedule and does the following:

- [x] Checks if there are new repositories in the [Door43 Catalog] organization
- [x] Triggers the webhook function for each new repository found.
- [x] Triggers the webhook function for queued items that are flaged as `dirty`.

### ts_v2_catalog

This function is run on a schedule and does the following:

- [x] Checks for a new v3 API catalog in the status table
- [x] Builds a v2 tS api from the new/updated v3 catalog.

### uw_v2_catalog

This function is run on a schedule and does the following:

- [x] Checks for a new v3 API catalog in the status table
- [x] Builds a v2 uW api from the new/updated v3 catalog.

### trigger

This function is run via AWS cron every 5 minutes and does the following:

- [x] Executes those function which run on a schedule. e.g. catalog, signing, etc.

## AWS Configuration

Here's a high level overview of the AWS configuration

### The following functions are configured as api endpoints within API Gateway:

* webhook: `/webhook`
* catalog: `/lambda/catalog`
* fork: `/lambda/fork`
* signing: `/lambda/signing`
* ts_v2_catalog: `/lambda/ts-v2-catalog`
* uw_v2_catalog: `/lambda/uw-v2-catalog`

For example you can trigger the fork lambda at `https://api.door43.org/v3/lambda/fork`.

> The functions are not designed to always return useful information in the browser and may timeout,
> however they are still running properly.

The name of the stage in API Gateway determines the operating environment.
If the stage name begins with `prod` the functions will operate on production databases.
If the stage name begins with anything other than `prod` the functions will
prefix databases with the stage name.

For example:

* a stage named `prod` would use the `d43-catalog-errors` db for reporting errors.
* a stage named `dev` would use the `dev-d43-catalog-errors` db for reporting errors.
* a stage named `test` would use the `test-d43-catalog-errors` db for reporting errors.

#### Stage Variables

* `cdn_bucket`
* `cdn_url`
* `to_email`
* `from_email`
* `api_bucket`
* `api_url`
* `gogs_url`
* `gogs_org`
* `gogs_token`
* `log_level` how noisy the logger should be. debug|info|warning|error
* `version` the api version

### acceptance function configuration

The `acceptance` function is ran according to a CloudWatch rule which runs when the catalog file is added to the api S3 bucket.

### trigger function configuration

The `trigger` function is ran according to a CloudWatch rule which is configured to run every 5 minutes via a cron job.

### Dynamo DB Configuration

The following database tables are used by the API pipeline described above.
Please note additional tables may be necessary when catering to multiple stages (described above).

* `d43-catalog-errors` tracks errors encountered in functions. Keyed with `lambda`.
* `d43-catalog-in-progress` tracks items in the queue. Keyed with `repo_name`.
* `d43-catalog-running` tracks functions that are running. This prevents certain functions from having multiple instances running at the same time. Keyed with `lambda`.
* `d43-catalog-status` tracks the status of the catalog generation. Keyed with `api_version`.

## Tools

###CSV to USFM3

This tool will convert a csv file containing Greek words to USFM 3 format.
You may execute the following command to learn how to use the tool.

```bash
python execute.py csvtousfm3 -h
```

[Door43 Catalog]:https://git.door43.org/Door43-Catalog