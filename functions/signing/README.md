## Encrypting a file using AWS CLI

This example encrypts the file `test.txt` and writes the results to `test.enc`: 

    aws kms encrypt --key-id arn:aws:kms:us-west-2:581647696645:key/guid-goes-here --plaintext fileb://test.txt --output text --query CiphertextBlob | base64 --decode > test.enc
