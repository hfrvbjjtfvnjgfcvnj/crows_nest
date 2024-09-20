""" Functionality for detecting aircraft of interest """
import os
import json
from datetime import datetime
import copy
from difflib import get_close_matches

import pyproj

directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE",
              "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


class Detector:
    """ Runtime configurable detection interface.
        Detections are made via rules supplied by JSON.
    """

    def __init__(self, json_file, loiter_det):
        self.loiter_det = loiter_det
        self.rules = self.load_definitions(json_file)
        self.geo = pyproj.Geod(ellps='WGS84')
        self.build_field_map()
        self.pending_intercepts = {}
        self.call_count = 0
        self.notifiers = []
        self.trackers = []
        self.alert_types = {}
        self.intercept_positions = []
        self.ignore_operators = []

    def load_data(self, json_file):
        """ load data from JSON """
        if json_file is None:
            f = open(os.path.join(json_file), encoding="utf-8")
        else:
            f = open(json_file, encoding="utf-8")
        data = json.load(f)
        f.close()
        return data

    def load_definitions(self, config_file):
        """ load detection definitions from JSON """
        return self.load_data(config_file)

    def get_rules(self):
        """ accessor """
        return self.rules

    def build_field_map(self):
        """ maps rule fields to indicies """
        fields = self.rules['fields']
        self.field_map = {}
        i = 0
        for field in fields:
            self.field_map[field] = i
            i = i+1

    def populate_alert_types(self, cursor):
        """ queries supported alert types from DB """
        if len(self.alert_types) > 0:
            # only run once
            return
        print("Loading alert types from database...")
        cursor.execute('select * from alert_type')
        for ret in cursor:
            print(f"Setting alert type '{ret[1]}' = '{ret[0]}'")
            self.alert_types[ret[1]] = ret[0]

    def populate_intercept_positions(self, config):
        """ pulls intercept ETA positions and metadata from config """
        self.intercept_positions = copy.deepcopy(
            config.get("alert_eta_positions", []))
        if config.get("alert_eta_station_position", False):
            pos = {}
            pos["latitude"] = config["station_latitude"]
            pos["longitude"] = config["station_longitude"]
            pos["enabled"] = True
            pos["name"] = "station"
            pos["radius_meters"] = config["alert_eta_radius_meters"]
            self.intercept_positions.append(pos)

    def populate_ignore_operators(self, cursor):
        """ queries ignored aircraft operators/registrants from the DB - these will not be alerted on """
        self.ignore_operators = []
        cursor.execute('select * from ignore_registrants')
        for ret in cursor:
            self.ignore_operators.append(ret[0])

    def perform_detections(self, config, timestamp, conn, cursor):
        """ called on a timer to perform detections based upon most recent observation data """
        self.call_count = self.call_count+1
        # a configurable 'frequency' for how often (as a number of calls), this function actually checks the DB
        # this may be desireable for low-ower/low-performance environments
        if self.call_count % config.get("detector_every_n_updates", 1) != 0:
            return
        self.call_count = 0

        self.populate_alert_types(cursor)
        self.populate_ignore_operators(cursor)
        self.populate_intercept_positions(config)

        new_notifications = []

        # check for loitering aircraft
        if config["alert_loiter"]:
            loitering_data = self.loiter_det.check_for_loiter(None)
            loitering_hex_strings = loitering_data.keys()
            if len(loitering_hex_strings) > 0:
                cursor.execute(
                    "CREATE OR REPLACE TABLE loiter_temp(hex CHAR(6) PRIMARY KEY)")
                for loiterer in loitering_hex_strings:
                    cursor.execute("INSERT INTO loiter_temp(hex) VALUES (?) ON DUPLICATE KEY UPDATE hex=?", (
                        loiterer.encode(), loiterer.encode()))
                conn.commit()
                rule = self.rules['loiter']
                self.queue_notifications(config, cursor, new_notifications,
                                         rule['query'], rule['detected_title'], rule['position_title'], rule['alert_type_name'])

        # check for intercepting aircraft
        self.detect_intercepts(config, cursor, new_notifications)

        # check for general aircraft types
        if len(config.get("alert_aircraft_type", "")) > 0:
            rule = self.rules['type']
            self.queue_notifications(config, cursor, new_notifications, rule['query'] % config["alert_aircraft_type"], rule['detected_title'] %
                                     config["alert_aircraft_type"], rule['position_title'] % config["alert_aircraft_type"], rule['alert_type_name'])

        # check for military aircraft
        if config["alert_military"]:
            rule = self.rules['military']
            self.queue_notifications(config, cursor, new_notifications,
                                     rule['query'], rule['detected_title'], rule['position_title'], rule['alert_type_name'])

        # check for special aircraft
        if config["alert_special"]:
            rule = self.rules['special']
            self.queue_notifications(config, cursor, new_notifications,
                                     rule['query'], rule['detected_title'], rule['position_title'], rule['alert_type_name'])

        # check for know/suspected "spook" (recon/intel) aircraft
        if config["alert_spook"]:
            rule = self.rules['spook']
            self.queue_notifications(config, cursor, new_notifications,
                                     rule['query'], rule['detected_title'], rule['position_title'], rule['alert_type_name'])

        # check for "interesting" aircraft
        # 'spook' is a subset of 'interesting', so don't do both notifications
        elif config["alert_interesting"]:
            rule = self.rules['interesting']
            self.queue_notifications(config, cursor, new_notifications,
                                     rule['query'], rule['detected_title'], rule['position_title'], rule['alert_type_name'])

        # check for government aircraft
        if config["alert_government"]:
            rule = self.rules['government']
            self.queue_notifications(config, cursor, new_notifications,
                                     rule['query'], rule['detected_title'], rule['position_title'], rule['alert_type_name'])

        for n in new_notifications:
            # print("NOTIFY: %s\n%s"%(n[0],n[2]))
            print(n)
            cursor.execute("insert into active_alerts(hex,first_seen,last_seen,alert_type) values(?,?,?,?) ON DUPLICATE KEY UPDATE last_seen=?, alert_type=? ",
                           (n[0], timestamp, timestamp, self.alert_types[n[3]], timestamp, self.alert_types[n[3]]))
            if config["alert_notifications"]:
                self.do_notification(config, n)

        self.update_trackers(cursor)

    def find_active_alert(self, cursor, hex_icao, alert_type_name):
        """ fetches any active alerts for the specified hex code.
            This check is performed relative to alert_type_name, and any alert with equivalent or higher priority is returned """
        cursor.execute("select * from active_alerts join alert_type on active_alerts.alert_type=alert_type.id join active_aircraft on active_alerts.hex=active_aircraft.hex where active_alerts.hex=? and alert_type.id <= (select id from alert_type where name=?)", (hex_icao, alert_type_name))
        return cursor.fetchall()

    def update_trackers(self, cursor):
        """ pass observations to all target trackers """
        # print("detector.update_trackers()")
        list_of_aircraft = self.fetch_active_alerts(cursor)
        for tracker in self.trackers:
            tracker.track_alert_aircraft(list_of_aircraft, self.field_map)

    def fetch_active_alerts(self, cursor):
        """ query all active alerts """
        cursor.execute(self.rules['active_alert']['query'])
        return cursor.fetchall()

    def should_ignore_operator(self, operator):
        """ helper to determine if an operator/registrant is on the ignore list """
        # check against ignore list and ignore the aircraft if the operator is on the ignore list
        if operator is not None:
            close_to = get_close_matches(
                operator, self.ignore_operators, cutoff=0.55)
            if close_to is not None and len(close_to) > 0:
                # print("IGNORING: '%s' due to '%s'"%(operator,close_to[0]))
                return True
            # print("ALLOWING: '%s'"%operator)
        return False

    def queue_notifications(self, config, cursor, new_notifications, query, detected_title, position_title, alert_type_name):
        """ 'programmable' call to queue a new notification into a 'new_notifications' list """
        # check for aircraft
        rows = []
        cursor.execute(query)
        rows = cursor.fetchall()
        for aircraft in rows:
            hex_icao = aircraft[0]
            lat = aircraft[3]
            lon = aircraft[4]
            distance = aircraft[5]

            # lookup any pre-existing active alert for this aircraft
            # this checks for any alert with type <= current alert type, allowing an escalation of notifications
            # if neede
            active_alert = self.find_active_alert(
                cursor, hex_icao, alert_type_name)

            # is this a new detection without an existing alert?
            is_new_alert = len(active_alert) == 0

            # pull aircraft operator to test against filters
            operator = aircraft[self.field_map['registrant_name']]

            if self.should_ignore_operator(operator):
                continue

            # does this detection have a position?
            has_position = ((lat is not None) and (
                lon is not None) and (distance is not None))

            if is_new_alert:
                if has_position:
                    if (config["alert_without_position"]) or (distance < config["alert_radius_meters"]):
                        new_notifications.append(
                            (aircraft[0], position_title, aircraft, alert_type_name))
                # should alert detections with no position data
                elif config["alert_without_position"]:
                    new_notifications.append(
                        (aircraft[0], detected_title, aircraft, alert_type_name))
            elif has_position:  # an alert alread exists on this aircraft
                # we only notify it if we do not already have a position in the previous alert
                alert_has_pos = ((active_alert[0][7] is not None) and (
                    active_alert[0][8] is not None))
                if not alert_has_pos:
                    new_notifications.append(
                        (aircraft[0], position_title, aircraft, alert_type_name))

    def detect_intercepts(self, config, cursor, new_notifications):
        """ checks all ETA intercept positions for potential intercept candidates """
        for pos in self.intercept_positions:
            self.detect_intercepts_at(config, cursor, new_notifications, pos)

    def detect_intercepts_at(self, config, cursor, new_notifications, pos):
        """ performs rough extrapolation for all active aircraft position/speed/heading data to determine if any intercepts of the given position are likely  """
        eta_lat = pos["latitude"]
        eta_lon = pos["longitude"]
        eta_name = pos["name"]
        rows = []
        rule = self.rules['active']
        cursor.execute(rule['query'])
        rows = cursor.fetchall()
        time_limit = 600
        time_step = 15

        alert_radius_m = pos["radius_meters"]
        latest_time = 0
        for aircraft in rows:
            lat = aircraft[self.field_map['latitude']]
            lon = aircraft[self.field_map['longitude']]
            speed_knots = aircraft[self.field_map['speed']]
            track = aircraft[self.field_map['track']]
            icao_type_description = aircraft[self.field_map['description']]
            time = aircraft[self.field_map['time']]
            operator = aircraft[self.field_map['registrant_name']]
            if self.should_ignore_operator(operator):
                continue
            if time > latest_time:
                latest_time = time
            if (lat is None) or (lon is None) or (speed_knots is None) or (track is None):
                continue

            if icao_type_description is not None:
                # get ICAO code (ex: L2J, H1T, etc) and extract first character as airframe type
                typecode = icao_type_description[0]
                typefilter = config.get("alert_eta_aircraft_type", "all")

                # if this type doesn't match the filter, skip the aircraft
                # "" and "all" match all codes
                if typefilter != "" and typefilter != "all" and typecode not in typefilter:
                    continue

            speed_meters_ps = speed_knots*0.514444  # 1 knot ~= 0.514444 mps

            rule = self.rules['intercept']
            for t in range(0, time_limit+1, time_step):
                # iterate over each time step in the detection range

                # estimate distance along track at each step
                proj_distance = speed_meters_ps*t

                # compute estimated position at each step
                plon, plat, _ = self.geo.fwd(lon, lat, track, proj_distance)

                # compute distance to estimated position
                _, _, proj_distance_m = self.geo.inv(
                    eta_lon, eta_lat, plon, plat)

                if proj_distance_m < alert_radius_m:
                    hex_icao = aircraft[self.field_map['hex']]

                    # lookup a previous pending detection
                    previous_det = self.pending_intercepts.get(hex_icao)

                    # config 'alert_eta_delay_filter_sec' represents how long an aircaft must be on an 'intercept' course before alerting
                    # if 'alert_eta_delay_filter_sec' is configured for 0 delay, or the current intercepting detection time exceeds 'alert_eta_delay_filter_sec', queue the notification
                    if (config["alert_eta_delay_filter_sec"] <= 0) or ((previous_det is not None) and (aircraft[self.field_map['time']] > previous_det[0] + config['alert_eta_delay_filter_sec'])):
                        self.queue_notifications(config, cursor, new_notifications, rule['query'] % aircraft[self.field_map['hex']], rule[
                                                 'detected_title'], f"{eta_name} - {rule['position_title']}", rule['alert_type_name'])
                    elif previous_det is not None:
                        # if we have a pending intercept, note it
                        # t0 = previous_det[0]
                        # t1 = aircraft[self.field_map['time']]
                        # dt = t1-t0
                        # df = config['alert_eta_delay_filter_sec']
                        # print("PENDING INTERCEPT: %s - t0=%d t1=%d dt=%d df=%d"%(hex,t0,t1,dt,df))
                        pending = list(self.pending_intercepts[hex_icao])
                        pending[5] = aircraft[self.field_map['time']]
                        pending = tuple(pending)
                        self.pending_intercepts[hex_icao] = pending
                    elif previous_det is None:
                        # if there is no previous notification, add a pending
                        # print("ADDING PENDING INTERCEPT: %s @ %d"%(hex,aircraft[self.field_map['time']]))
                        self.pending_intercepts[hex_icao] = (aircraft[self.field_map['time']], rule['query'] % aircraft[self.field_map['hex']],
                                                             rule['detected_title'], f"{eta_name} - {rule['position_title']}", rule['alert_type_name'], aircraft[self.field_map['time']])

                    # keep track of the pending aircraft that are 'still' on intercept courses so we can cleanup pending_intercepts
                    break

        # cleanup pending_intercepts to remove any records of aircraft no longer on intercept courses
        keys = self.pending_intercepts.keys()
        purge = []

        for key in keys:
            # if key not in still_intercepting:
            if self.pending_intercepts[key][5] + config['alert_eta_delay_filter_sec'] < latest_time - 10:
                # print("EXPIRING %s time=%d delay=%d limit=%d"%(key,self.pending_intercepts[key][5],config['alert_eta_delay_filter_sec'],latest_time+10))
                purge.append(key)
        # remove keys in purge list
        for key in purge:
            # print("POPPING: %s"%key)
            self.pending_intercepts.pop(key)

    def do_notification(self, config, data):
        """ forward notifications to all notifiers """
        sound = None
        priority = 0

        # notification data
        # hex_icao = data[0]   #UNUSED
        title = data[1]
        aircraft = data[2]
        alert_type_name = data[3]

        # notification sound
        sound = self.note_sound(config, aircraft, alert_type_name)

        if sound is None:
            sound = alert_type_name

        text = self.note_text(config, aircraft, alert_type_name)
        url = self.note_url(config, aircraft)

        for notifier in self.notifiers:
            notifier(config, title, text, priority,
                     alert_type_name, sound, url)

    def add_notifier(self, notifier_functor):
        """ adds a notifier """
        self.notifiers.append(notifier_functor)

    def add_tracker(self, tracker):
        """ adds a tracker """
        self.trackers.append(tracker)

    def note_sound(self, _, aircraft, alert_type_name):
        """ uses loaded detection rules to map a notification aircraft and alert_type_name to an appropriate notification sound """
        if aircraft is None:
            return None

        sound = None

        # first apply rules for special alert type sounds
        keys = self.rules['sounds_alert_type'].keys()
        for key in keys:
            if alert_type_name == key:
                sound = self.rules['sounds_alert_type'][key]
                return sound

        icao_description = aircraft[self.field_map['description']]
        if icao_description is None:
            return None

        # next apply rules for description (airframe) sounds
        keys = self.rules['sounds_airframe'].keys()
        for key in keys:
            if icao_description[0] == key:
                sound = self.rules['sounds_airframe'][icao_description[0]]
                return sound

        # next apply rules for description (engine) sounds
        keys = self.rules['sounds_engine'].keys()
        for key in keys:
            if icao_description[2] == key:
                sound = self.rules['sounds_engine'][icao_description[2]]
                return sound

        return None

    def bearing_to_direction(self, bearing):
        """ maps 0-360deg -> text shorthand ex: 'NNW' or 'SE' for notication readability """
        while bearing < 0:
            bearing += 360
        while bearing >= 360:
            bearing -= 360
        index = int(bearing/22.5)
        return directions[index]

    def note_url(self, _, aircraft):
        """ attempts to construct an aircraft image URL using adsbexchange """
        aircraft_type = aircraft[self.field_map['icao_type_code']]
        url = f"https://globe.adsbexchange.com/aircraft_sil/{aircraft_type}.png"
        return url

    def note_text(self, config, aircraft, _):
        """ constructs a notification's text body """
        # print("--------------------")
        # print(aircraft)
        # print("--------------------")
        model = 'Unknown'
        time = datetime.fromtimestamp(
            aircraft[self.field_map['time']]).strftime('%Y-%m-%d %H:%M:%S')
        distance_miles = aircraft[self.field_map['distance']]/1609.34
        bearing = aircraft[self.field_map['bearing']]
        bearing_str = self.bearing_to_direction(
            aircraft[self.field_map['bearing']])
        hex_icao = aircraft[self.field_map['hex']]
        lat = aircraft[self.field_map['latitude']]
        lon = aircraft[self.field_map['longitude']]
        registration = aircraft[self.field_map['registration']]
        operator = aircraft[self.field_map['registrant_name']]
        model = aircraft[self.field_map['icao_name']]
        icao_type_description = aircraft[self.field_map['description']]
        faa_type_aircraft = aircraft[self.field_map['faa_type_name']]
        comment = aircraft[self.field_map['comment']]
        # if we have a comment (ex: 'SPY PLANE')
        if comment is None:
            comment = ""
        else:
            comment = f"Comment: {comment}\n"

        local_url = config["dump1090_local_url"]
        feed_url = f"https://globe.adsbexchange.com/?feed={config['adsb_exchange_feed_code']}"
        icao_url = f"https: // globe.adsbexchange.com /?icao={hex_icao}"

        text = f"{comment}Operator: {operator}\nTime: {time}\nModel: {model}\nDistance: {distance_miles:.2f} miles\nReg: {registration}\nBearing: {bearing} ({bearing_str})\nHex Code: {hex_icao}\nLatitude: {lat}\nLongitude: {lon}\nICAO Type: {icao_type_description}\nFAA Type: {faa_type_aircraft}\n{local_url}\n{feed_url}\n{icao_url}"
        return text
