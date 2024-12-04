#!/bin/bash

DIR_CE="onlyoffice-ds"
DIR_DE="onlyoffice-ds-integration"

generate_command() {
  local dir=$1
  local files=("$dir"/*) 
  local command="$appcenterctl upload $credentials --noninteractive $appver \\"
  
  for file in "${files[@]}"; do
    command+="\ $file \\"
  done
  
  echo -e "${command::-2}"
}

echo "generate_command "$DIR_CE""

#generate_command "$DIR_DE"
