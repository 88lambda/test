#!/bin/bash

DIRECTORY="onlyoffice-ds"


if [[ ! -d "$DIRECTORY" ]]; then
    echo "no such dir"
    exit 1
fi

FILES=$(find "$DIRECTORY" -type f)

if [[ -z "$FILES" ]]; then
    echo "dir is empty"
    exit 1
fi

COMMAND="./univention-appcenter-control upload --username ${{ secrets.PORTAL_USER }} --pwdfile ./pwdfile --noninteractive $appver"
for FILE in $FILES; do
    COMMAND+=" \\$'\n           $FILE'"
done

echo -e "$COMMAND"

# eval "$COMMAND"
