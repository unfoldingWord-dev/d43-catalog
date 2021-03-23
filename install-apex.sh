#!/usr/bin/env bash

LATEST=$(curl -s https://api.github.com/repos/apex/apex/tags | grep -Eo '"name":.*?[^\\]",'  | head -n 1 | sed 's/[," ]//g' | cut -d ':' -f 2)
echo $LATEST
URL="https://github.com/apex/apex/releases/download/${LATEST}/apex_linux_amd64"
echo $URL

curl -sL ${URL} -o ./apex
ls -l ./apex
chmod +x ./apex
