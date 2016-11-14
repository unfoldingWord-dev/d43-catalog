#!/usr/bin/env bash

set -e

for file in `ls functions/*/requirements.txt`
do
  pip install --upgrade -r $file -t `dirname $file` 
done
