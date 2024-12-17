#!/bin/bash

ucsver="5.0"
app_ver="$APP_VER"
appcenterctl=~/univention-appcenter-control

if [ ! -f $appcenterctl ]; then
    curl https://provider-portal.software-univention.de/appcenter-selfservice/univention-appcenter-control --output $appcenterctl
    chmod +x $appcenterctl
fi

app_ini=$(find . -maxdepth 1 -name "*.ini" | head -n 1)
app_name=$(basename "$app_ini" .ini)

if [ -z "$app_ini" ]; then
    echo -e "No ini files found. Nothing to publish"
    exit 1
fi

sed -i "s|appversion|$app_ver|" "$app_ini"
sed -i "s|imageversion|$app_ver|" "$app_ini"

echo -e $appcenterctl new-version $credentials $ucsver/$app_name $ucsver/$app_name=$version

file_list=$(ls)
common_files=$(ls($(ln -s "../../common" ~/common))

$appcenterctl upload $credentials --noninteractive $ucsver/$app_name=$version $file_list $common_files
