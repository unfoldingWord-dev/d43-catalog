const AWS = require('aws-sdk');
const apiHelpers = require('./helpers/apiHelpers');
const parseHelpers = require('./helpers/parseHelpers');

exports.handle = async function(e, ctx, cb) {
  const catalog = await apiHelpers.getCatalog();
  const res = parseHelpers.pivotOnKey(catalog, 'subject');
  cb(null, res)
}