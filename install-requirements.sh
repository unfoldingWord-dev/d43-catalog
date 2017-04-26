#!/usr/bin/env bash

set -e

# install dependencies
for file in `ls functions/*/requirements.txt`
do
  pip install --upgrade -r $file -t `dirname $file` 
done

# copy shared tools
pip install --upgrade -r tools/requirements.txt -t tools
for dir in `ls -d functions/*/`
do
  cp -R tools $dir
done
