const apiHelpers = require('./helpers/apiHelpers');
const parseHelpers = require('./helpers/parseHelpers');

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