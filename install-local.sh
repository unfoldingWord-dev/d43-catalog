#!/usr/bin/env bash

set -e

for dir in `ls -d functions/*`
do
  cp -R /c/web/tx-shared-tools/*_* $dir
  cp -R /c/web/tx-manager/*_* $dir
done
