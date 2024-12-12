#!/bin/bash

ucsver="5.0"
app_ver="$APP_VER"

if [ ! -f "univention-appcenter-control" ]; then
    curl -O https://provider-portal.software-univention.de/appcenter-selfservice/univention-appcenter-control 
    chmod +x univention-appcenter-control
fi

app_ini=$(find . -maxdepth 1 -name "*.ini" | head -n 1)
app_name=$(basename "$app_ini" .ini)
echo -e $app_name

if [ -z "$app_ini" ]; then
    exit 1
fi

version=$app_ver

echo -e sed -i 's|appversion|$version|' "$app_ini"
echo -e sed -i 's|imageversion|$version|' "$app_ini"

echo -e $appcenterctl new-version $credentials $ucsver/$app_name $ucsver/$app_name=$version

file_list=$(ls)

$appcenterctl upload $credentials --noninteractive $ucsver/$app_name=$version $file_list
