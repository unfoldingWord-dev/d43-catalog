#!/usr/bin/env bash

LATEST=$(curl -s https://api.github.com/repos/apex/apex/tags | grep -Eo '"name":.*?[^\\]",'  | head -n 1 | sed 's/[," ]//g' | cut -d ':' -f 2)
URL="https://github.com/apex/apex/releases/download/${LATEST}/apex_linux_amd64"

curl -sL ${URL} -o ./apex
chmod +x ./apex
