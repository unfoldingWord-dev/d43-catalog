master:
[![Build Status](https://travis-ci.org/unfoldingWord-dev/d43-catalog.svg?branch=master)](https://travis-ci.org/unfoldingWord-dev/d43-catalog) 
[![Coverage Status](https://coveralls.io/repos/github/unfoldingWord-dev/d43-catalog/badge.svg?branch=master)](https://coveralls.io/github/unfoldingWord-dev/d43-catalog?branch=master)

develop:
[![Build Status](https://travis-ci.org/unfoldingWord-dev/d43-catalog.svg?branch=develop)](https://travis-ci.org/unfoldingWord-dev/d43-catalog) 
[![Coverage Status](https://coveralls.io/repos/github/unfoldingWord-dev/d43-catalog/badge.svg?branch=develop)](https://coveralls.io/github/unfoldingWord-dev/d43-catalog?branch=develop)

# d43-catalog

These are the AWS Lambda functions for generating the [API v3 catalog endpoint](https://api.door43.org/v3/catalog) from the [Door43 Resource Catalog](https://git.door43.org/Door43-Catalog) organization in our Door43 Git Service.

Requires the [tx-manager library](https://github.com/unfoldingWord-dev/tx-manager).

## How it Works

When a new repository is added or forked into the [Door43 Resource Catalog](https://git.door43.org/Door43-Catalog) organization a chain reaction is started that eventually adds the content into our API v3 catalog endpoint](https://api.door43.org/v3/catalog), assuming all the checks passed.  Here is an overview:

1. Someone creates a new repo or forks a repo into the [Door43 Resource Catalog](https://git.door43.org/Door43-Catalog) organization
1. A webhook for the organization notifies the Lambda pipeline of new or updated content
1. The Lambda pipeline:
  * Grabs the content and deciphers metadata
  * Adds entry into an "in progress" database table
  * Puts the files to be signed on S3 in the cdn.door43.org bucket, keyed with `temp/<repo-name>/<commit-hash>/<filename>`
  * The upload to S3 triggers a digital signing routine for our systems that use cryptographic verification and puts it on S3 as `cdn.door43.org/<lang>/<resource>/v<version>/<filename>`
  * A cron job on AWS triggers the catalog.json generator (Lambda) ever 5 minutes. If there are new changes to the "in progress" DB, and all files have been signed and all JSON checks out, it copies the new catalog.json to the (S3) API endpoint

## Function Description

The following provides a functional description of the functions in this repository.

### webhook 

This is the first function that is called by the organization's webhook and it does the following:

* [x] Accept webhook from Gogs org (need to test the org webhook)
* [x] Load manifest files from repo to be added/modified (via HTTPS)
* [x] Format correctly new entries, per https://github.com/unfoldingWord-dev/door43.org/wiki/API-v3-Resource-Catalog-Endpoint#catalog-structure (assume input manifest looks like http://resource-container.readthedocs.io/en/latest/manifest.html )
* [x] Save to the In Progress database table, with timestamp
* [x] Copy data in `formats` key into S3 bucket cdn.door43.org/temp/ to be signed
* [x] Change in above S3 bucket triggers signing lambda for each file

Built in https://github.com/unfoldingWord-dev/door43.org/issues/257.

### signing

This is the second fuction, which is triggered by changes in the S3 bucket referenced above, it does the following:

- [x] Signs a single file in S3 bucket (cdn.door43.org/temp/) (which was written by webhook function above)
- [x] Verifies that signature checks out
- [x] Move data file out of /temp/ into correct directory... cdn.door43.org/[lang]/[slug]/[content_ver]/[format_type]/[file]
- [x] Upload the signature as `.sig` file in above directory
- [x] Add signature URL to the In Progress DB (this part blocked by #257 )
- [x] Update data URL in the In Progress DB

Built in https://github.com/unfoldingWord-dev/door43.org/issues/247

### catalog

This function is run via AWS cron every 5 minutes and it does the following:

- [x] Consistency check on In Progress DB
  - [x] If it's not consistent it fails
    - [x] Sigs are missing == inconsistent
    - [x] Incorrect formatting ==  inconsistent
    - [x] If it fails increment a integer in a DB table
    - [x] If fail integer > 4, send an email (ask Jesse where to send)
  - [x] If it is consistent, zero the failed DB table
- [x] Copy the rows from In Progress DB to Production DB
  - [x] Never overwrite
  - [x] Use timestamps as keys (to support specific date querying at a later date)
- [x] Saves latest Production DB to `catalog.json` on S3 bucket
- [x] Update to S3 file triggers acceptance test below

Built in https://github.com/unfoldingWord-dev/door43.org/issues/258

### acceptance-test

After a new catalog file is written to S3, this function does the following:

- [x] Make sure structure of catalog file is correct
- [x] Make HEAD request for each resource (every URL) in catalog to verify it exists
- [x] Emails any errors to the specified email addresses

Technically this is all duplicate testing of what we are alreadying doing elsewhere in the pipeline.  This function is the "oops" catcher.

Built in https://github.com/unfoldingWord-dev/door43.org/issues/242

## Historical Information

Many of the original issues created for this pipeline are in https://github.com/unfoldingWord-dev/door43.org/milestone/9?closed=1 or https://github.com/unfoldingWord-dev/door43.org/issues?q=is%3Aopen+is%3Aissue+label%3AAPI.  One of the initial meta issues was https://github.com/unfoldingWord-dev/door43.org/issues/206.
