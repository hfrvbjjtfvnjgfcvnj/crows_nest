#!/bin/bash

TMP="$(mktemp -d)"
echo "Using temp: ${TMP}"
DIR="$(dirname "$(realpath "${0}")")"
echo "Running script in: ${DIR}"

wget -O "${TMP}/db.zip" https://registry.faa.gov/database/ReleasableAircraft.zip && cd "${TMP}" && unzip ./db.zip && rsync -va *.txt /opt/crows_nest/ && echo "update_crows_nest.sh" >> /opt/crows_nest/update.log && date >> /opt/crows_nest/update.log

sed -i 's/  */ /g;s/ *,/,/g;s/\r//g;s/,$//g' /opt/crows_nest/MASTER.txt
cat /opt/crows_nest/MASTER.txt | cut -f1,7 -d ','  > /opt/crows_nest/OWNER_INDEX.txt
grep 'DEPT\|DEPARTMENT\|POLICE\|SHERRIF\|COUNTY\|STATE\|CITY OF\|DISTRICT\|ADMINISTRATION\|AGENCY' /opt/crows_nest/OWNER_INDEX.txt | grep -v " LLC\| INC\| BANK\|INSURANCE\|UNIVERSITY\|COLLEGE\|REAL ESTATE\|CLUB\| LLP" | sed 's/ *$//g' > /opt/crows_nest/GOVT_RECORDS.txt

cut -f1,7 -d ',' /opt/crows_nest/MASTER.txt | grep -i ' AIR FORCE\| NAVY\| ARMY\| COAST GUARD' | grep -v 'CLUB\| INC\| LLC\| MUSEUM\|FRIENDS\| FOUNDATION\| CORPS OF ENGINEERS\|COMMEMORATIVE\|ASSOCIATION' > /opt/crows_nest/MIL_RECORDS.txt

pushd "${DIR}" 2>/dev/null 1>/dev/null
USER="$(grep 'db_username' config.json | cut -f2 -d ":" | sed 's/^"//;s/",$//')"
CRED="$(grep 'db_password' config.json | cut -f2 -d ":" | sed 's/^"//;s/",$//')"
ret=0;
if [ -z "${CRED}" ] ;
then
	echo "ERROR: Unable to load DB credentials. Aborting."
	ret=-1;
else
	mysql -u "${USER}" -p"${CRED}" -e 'source gov_records.sql'
	popd 2>/dev/null 1>/dev/null
fi

rm -rfv "${TMP}"
exit ${ret}
