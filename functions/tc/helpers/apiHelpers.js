var request = require('request');
const AWS = require('aws-sdk');
const API_ORIGIN = process.env.API_ORIGIN || 'api.door43.org';
const DCS_API = `https://${API_ORIGIN}`;
const CATALOG_PATH = '/v3/catalog.json';

/**
 * Performs a get request on the specified url.
 * This function trys to parse the body but if it fails
 * will return the body by itself.
 *
 * @param {string} url - Url of the get request to make
 * @return {Promise} - parsed body from the response
 */
function makeRequest(url) {
  return new Promise((resolve, reject) => {
    request(url, function(error, response, body) {
      if (error)
        reject(error);
      else if (response.statusCode === 200) {
        let result = body;
        try {
          result = JSON.parse(body);
        } catch (e) {
          reject(e);
        }
        resolve(result);
      }
    });
  });
}

/**
 * Request the catalog.json from DCS API
 * @return {Object} - Catalog from the DCS API
 */
function getCatalog() {
  return makeRequest(DCS_API + CATALOG_PATH);
}

function uploadToS3(Key, data) {
  return new Promise((resolve, reject) => {
    var s3 = new AWS.S3();
    var base64data = Buffer.from(JSON.stringify(data), 'utf8');
    var params = {
      Bucket: API_ORIGIN,
      Key,
      Body:base64data,
      ContentType:'text/html; charset=utf-8'
    };
    s3.putObject(params, function(err, res) {
      if (err) {
        console.log("Error uploading data: ", err);
        reject(err)
      } else {
        resolve()
      }
    });
  });
}

module.exports = {
  getCatalog,
  makeRequest,
  uploadToS3
}
