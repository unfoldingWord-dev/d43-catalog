const apiHelpers = require('./helpers/apiHelpers');
const parseHelpers = require('./helpers/parseHelpers');

/**
 * This endpoint will be called after a trigger in the s3 bucket api.door43.org/v3/catalog.json
 * This endpoint creates a pivoted.json as well as indivual keys for the subjects in a resource
 * This endpoint also creates a index.json which lists all enpoints available
 * @param {Object} e - Event given from AWS Lambda
 * @param {Object} ctx - Context given from AWS Lambda
 * @param {Function} cb - Callback for response of Lambda function
 */
exports.handle = async function(e, ctx, cb) {
  try {
    const catalog = await apiHelpers.getCatalog();
    const {pivoted, index, subject} = parseHelpers.pivotOnKey(catalog, 'subject');
    await apiHelpers.uploadToS3('v3/subjects/index.json', index)
    await apiHelpers.uploadToS3('v3/subjects/pivoted.json', pivoted)
    Object.keys(subject).forEach(async (key) => {
      await apiHelpers.uploadToS3(`v3/subjects/${key}.json`, subject[key])
    })
  } catch(e) {
    console.log(e);
  }
  cb(null, 'OK')
}