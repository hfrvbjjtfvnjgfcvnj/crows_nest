# Crow's Nest

Monitor, data logger, and alert generator for dump1090-mutability.

## Description

Crow's Nest is a Python systemd service for tracking, logging, and parsing the outputs of [dump1090-mutability](https://github.com/adsbxchange/dump1090-mutability) (it may work with other variants of dump1090, but I have not tested this). This package is designed to comapare locally received and decoded ADS-B aircraft tracking data to public aircraft databases and generate alert notifications if/when aircraft of interest are detected within range of your ADS-B receiver. 

Package includes utility scripts for updating the Crows Nest internal aircraft database from the FAA aircraft registry and from community aircraft information using [tar1090-db](https://github.com/wiedehopf/tar1090-db).

## Purpose

Crow's Nest is envisioned to be a real-time alert system for local ADS-B receiver data. Crow's Nest actively monitors the aircraft detected via dump1090-mutability and compares the ICAO hex codes to a local database. Alerts can be configured for any combination of military aircraft, aircraft registered to government organizations, and/or "special" aircraft designated by the user (ex: notification when a buddy's NXXXXX flies by).

## Vision

Current implementation utilizes [pushover](https://pushover.net) notifications. In the future I want to expand to enable additional notification options. I particularly want to explore options for local alert notifications (via audio or radio) without the need for a third-party service.

## Getting Started

### Dependencies

Tested on Ubuntu 22.04.

Requires:
mariadb to be preinstalled and configured

### Installing and Running

0) Ensure [dump1090-mutability](https://github.com/adsbxchange/dump1090-mutability) is running
1) Clone repo however you see fit
2) sudo ./setup.sh
3) customize /opt/crows_nest/config.json
4) sudo systemctl start crows_nest.service
5) (optional) use crontab -e to call update_aircraft_db.sh and/or update_tar1090-db.sh to refresh reference data

## License

This project is licensed under the GNU General Public License v3.0 License - see the LICENSE.md file for details

## TODO

- Sub-categorize government aircraft (federal, state, local)
- Expand notification options

## Acknowledgments

* [tar1090-db](https://github.com/wiedehopf/tar1090-db)
* [dump1090-mutability](https://github.com/adsbxchange/dump1090-mutability)
* [https://github.com/Wyattjoh/pushover](https://github.com/Wyattjoh/pushover)
