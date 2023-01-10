#!/bin/bash

DIR="$(dirname "${0}")"
cd "${DIR}"

USER="$(whoami)"
if [ 'root' != "${USER}" ] ;
then
	echo "ERROR: setup.sh must be run as root."
	exit 1
fi

if id crows_nest;
then
	echo "Warning: 'crows_nest' user exists. Not creating a new one."
else
	useradd -r -s /bin/false crows_nest
	echo "Created user: 'crows_nest'"
fi

echo "Installing to /opt/crows_nest"
if [ -d "/opt/crows_nest" ] ;
then
	echo "Warning: '/opt/crows_nest' already exists. This should be OK, but make note incase somethings breaks."
fi
mkdir -p /opt/crows_nest
chown -R crows_nest /opt/crows_nest

echo "Installing Python3 requirements..."
if [ -e "/opt/crows_nest/venv" ] ;
then
	rm -rfv "/opt/crows_nest/venv"
fi
python3 -m venv /opt/crows_nest/venv
source /opt/crows_nest/venv/bin/activate
/opt/crows_nest/venv/bin/pip3 install -r requirements.txt

./update_aircraft_db.sh
./update_tar1090-db.sh
cp *.py *.sh /opt/crows_nest/
if [ -f /opt/crows_nest/config.json ] ;
then
	echo "Warning: Config file '/opt/crows_nest/config.json' already exists. Not installing a new one"
else
	cp config.json.example /opt/crows_nest/config.json
fi
chown -R crows_nest /opt/crows_nest/

USER="$(grep 'db_username' config.json | cut -f2 -d ":" | sed 's/^"//;s/",$//')"
CRED="$(grep 'db_password' config.json | cut -f2 -d ":" | sed 's/^"//;s/",$//')"

mysql -u "${USER}" -p"${CRED}" -e 'source crows_nest.sql'

cp crows_nest.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable crows_nest.service

echo "NOTE: Update /opt/crows_nest/config.json prior to starting crows_nest service."

