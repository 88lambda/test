#!/bin/bash

ucsver="5.0"
app_ver="$APP_VER"
PY_SCRIPT_PATH="$(dirname "$(realpath "$0")")/../publish_script.py"

if [ ! -f "publish_script.py" ]; then
    curl -O https://provider-portal.software-univention.de/appcenter-selfservice/univention-appcenter-control 
    chmod +x univention-appcenter-control
fi

app_ini=$(find . -maxdepth 1 -name "*.ini" | head -n 1)
app_name=$(basename "$app_ini" .ini)

if [ -z "$app_ini" ]; then
    exit 1
fi

version=$app_ver

sed -i 's|appversion|$version|' "$app_ini"
sed -i 's|imageversion|$version|' "$app_ini"

file_list=$(ls | tr '\n' ',') 


python3 "$PY_SCRIPT_PATH" "$ucsver/$app_name" "$ucsver/$app_name=$version" "$file_list"
