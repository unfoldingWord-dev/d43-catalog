const AWS = require('aws-sdk');
const apiHelpers = require('./helpers/apiHelpers');

exports.handle = function(e, ctx, cb) {
  apiHelpers.getCatalog().then((res)=>{
    cb(null, res)
  })
}