#!/bin/bash

ucsver="5.0"
app_ver="$APP_VER"
pwd="$PASS"

if [ ! -f "../univention-appcenter-control" ]; then
    cd .. && { curl -O https://provider-portal.software-univention.de/appcenter-selfservice/univention-appcenter-control ; chmod +x univention-appcenter-control ; cd -; }
fi

if [ ! -f "../pwdfile" ]; then
    cd .. && { echo "$pwd" > pwdfile ; cd -; }
fi

app_ini=$(find . -maxdepth 1 -name "*.ini" | head -n 1)
app_name=$(basename "$app_ini" .ini)

if [ -z "$app_ini" ]; then
    echo -e "No ini files found. Nothing to publish"
    exit 1
fi

sed -i "s|appversion|$app_ver|" "$app_ini"
sed -i "s|imageversion|$app_ver|" "$app_ini"

$appcenterctl new-version $credentials $ucsver/$app_name $ucsver/$app_name=$version

file_list=$(ls)
common_files=$(find "../../common" -type f -exec realpath {} \;)

$appcenterctl upload $credentials --noninteractive $ucsver/$app_name=$version $file_list $common_files
