#!/bin/bash

chown -R ds:ds /var/lib/onlyoffice/documentserver/App_Data/cache/files
JSON=/var/www/onlyoffice/documentserver/npm/json
${JSON} -q -f /etc/onlyoffice/documentserver/default.json -I -e "this.services.CoAuthoring.requestDefaults.rejectUnauthorized=false"

exit 0