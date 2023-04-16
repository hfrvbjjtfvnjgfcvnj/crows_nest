# Crow's Nest

Monitor, data logger, and alert generator for dump1090-mutability.

## Description

Crow's Nest is a Python systemd service for tracking, logging, and parsing the outputs of [dump1090-mutability](https://github.com/adsbxchange/dump1090-mutability) (it may work with other variants of dump1090, but I have not tested this). This package is designed to comapare locally received and decoded ADS-B aircraft tracking data to public aircraft databases and generate alert notifications if/when aircraft of interest are detected within range of your ADS-B receiver. 

Package includes utility scripts for updating the Crows Nest internal aircraft database from the FAA aircraft registry and from community aircraft information using [tar1090-db](https://github.com/wiedehopf/tar1090-db).

## Purpose

Crow's Nest is envisioned to be a real-time alert system for local ADS-B receiver data. Crow's Nest actively monitors the aircraft detected via dump1090-mutability and compares the ICAO hex codes to a local database. Alerts can be configured for any combination of military aircraft, aircraft registered to government organizations, and/or "special" aircraft designated by the user (ex: notification when a buddy's NXXXXX flies by).

The goal is to provide a flexible and extensible toolbox for automatically filtering and whittling down a cacophony of ADS-B data into actionable snippets.

## Technical Approach

Development has a taken a "breadth-first" approach to getting an assortment of features enabled to explore what is possible and what is actually useful. Every attempt has been made to expose as many options as configuration settings as possible to allow tuning the internal algorithms for the individual user's situation.

Crows Nest currently supports two plug-in interfaces for collaborative expansion:
1) Notifiers - Plug-ins that get called when a new aircraft detection (matching the user's configuration settings) is made.
2) Trackers - Plug-ins that get called periodically and are provided updated tracking information on previously detected and alerted aircraft.

## Available Plug-ins
Notifiers
- pushover_notifier (built-in) - Utilizes [pushover](https://pushover.net) cloud-based push notifications. This allows sending push notifications to mobile devices, and is included with Crow's Nest as an example Notifier.
- [tak_notifier](https://github.com/hfrvbjjtfvnjgfcvnj/crows_nest-tak_notifier) - Forwards alert notifications to a TAK server as a geochat message.
- [festival_notifier](https://github.com/hfrvbjjtfvnjgfcvnj/crows_nest-festival_notifier) - Utilizes the FOSS [festival](http://festvox.org/festival/) library to generate audio notifications via text-to-speech synthesis. Generated audio files can then forwarded to another host for audio playback via loudspeaker or transmitted via radio.

Trackers
- [tak_tracker](https://github.com/hfrvbjjtfvnjgfcvnj/crows_nest-tak_notifier) - Implemented along side tak_notifier. Automatically generates CoT PLI data for tracked alert aircraft and forwards those CoT to a TAK server for distribution.

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
