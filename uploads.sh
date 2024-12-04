#!/bin/bash

curl -O https://provider-portal.software-univention.de/appcenter-selfservice/univention-appcenter-control
chmod +x univention-appcenter-control

DIR_CE="onlyoffice-ds"
DIR_DE="onlyoffice-ds-integration"

generate_command() {
  local dir=$1
  local files=("$dir"/*) 
  local command="./univention-appcenter-control upload --username ./username --pwdfile ./pwdfile --noninteractive 5.0/onlyoffice-ds=8.2.1.1.27 \\"
  
  for file in "${files[@]}"; do
    command+="\n           $file \\"
  done
  
  echo -e "${command::-2}"
}

generate_command "$DIR_CE"

generate_command "$DIR_DE"
