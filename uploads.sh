#!/bin/bash

DIR_CE="onlyoffice-ds"
DIR_DE="onlyoffice-ds-integration"

generate_command() {
  local dir=$1
  local files=("$dir"/*) 
  local command="./univention-appcenter-control upload --username ${{ secrets.PORTAL_USER }} --pwdfile ./pwdfile --noninteractive 5.0/onlyoffice-ds=${{ inputs.ver }} \\"
  
  for file in "${files[@]}"; do
    command+="\n           $file \\"
  done
  
  echo -e "${command::-2}"
}

generate_command "$DIR_CE"

generate_command "$DIR_DE"
