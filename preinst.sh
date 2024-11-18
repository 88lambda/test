#!/bin/bash

set -e
mkdir -p /var/lib/univention-appcenter/apps/onlyoffice-ds/Data/certs
cp /etc/univention/ssl/$(hostname)/cert.pem /var/lib/univention-appcenter/apps/onlyoffice-ds/Data/certs/onlyoffice.crt
cp /etc/univention/ssl/$(hostname)/private.key /var/lib/univention-appcenter/apps/onlyoffice-ds/Data/certs/onlyoffice.key
cp /etc/postfix/dh_2048.pem /var/lib/univention-appcenter/apps/onlyoffice-ds/Data/certs/dhparam.pem
chmod 640 /var/lib/univention-appcenter/apps/onlyoffice-ds/Data/certs/*
ucr set appcenter/apps/onlyoffice-ds/docker/params='-t -e JWT_ENABLED=false'

exit 0