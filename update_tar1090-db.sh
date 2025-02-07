#!/bin/bash

source /opt/crows_nest/venv/bin/activate

URL='https://github.com/wiedehopf/tar1090-db.git'
GITDIR="$(mktemp -d)/tar1090-db"

DIR="$(dirname "$(realpath "${0}")")"
cd "${DIR}"

if [ -d "${GITDIR}" ] ;
then
	rm -rfv "${GITDIR}"
fi

git clone "${URL}" "${GITDIR}"

pushd "${GITDIR}"

cp icao_aircraft_types.json "${DIR}/"

git checkout csv

gunzip aircraft.csv.gz

mv aircraft.csv "${DIR}/"

popd

cp icao_type_descriptions.sql tar1090-db.sql /opt/crows_nest/

python3 load_icao_type_descriptions.py > /opt/crows_nest/icao_type_descriptions.csv

cat aircraft.csv | cut -f1,2,3,5 -d ';' | sed 's/;/,/g;s/,/./5;s/,/./4;s/  *,/,/g;s/,  */,/g;' > /opt/crows_nest/tar1090-db.csv

sed -i 's/,RV-12,/,RV12,/g' /opt/crows_nest/tar1090-db.csv

USER="$(grep 'db_username' config.json | cut -f2 -d ":" | sed 's/^"//;s/",$//')"
CRED="$(grep 'db_password' config.json | cut -f2 -d ":" | sed 's/^"//;s/",$//')"

mysql -u "${USER}" -p"${CRED}" crows_nest -e 'source /opt/crows_nest/icao_type_descriptions.sql; source /opt/crows_nest/tar1090-db.sql;'

rm icao_aircraft_types.json

rm -rf "${GITDIR}"

