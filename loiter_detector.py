""" analyzes aircraft track history to try to detect loitering (suspicious) aircraft """
import time
import pyproj
from loiter import is_continuous, is_loiter

LOITER_DEGREES_DEFAULT = 360
LOITER_TRIGGER_DURATION_DEFAULT = 9999999
LOITER_AIRCRAFT_TYPE_DEFAULT = "*"


class LoiterDetector:
    """ basic loiter detector """

    def __init__(self) -> None:
        self.nav_records = {}
        self.debug = True
        self.debug_time = time.time()
        self.debug_interval_sec = 60
        self.loiter_degrees = LOITER_DEGREES_DEFAULT
        self.loiter_trigger_duration = LOITER_TRIGGER_DURATION_DEFAULT
        self.loiter_aircraft_type = LOITER_AIRCRAFT_TYPE_DEFAULT
        self.geo = pyproj.Geod(ellps='WGS84')
        self.loiter_exclusions = []

    def configure(self, config_dict):
        """ pull configuration parameters from config """
        self.loiter_degrees = config_dict.get(
            "alert_loiter_degrees", LOITER_DEGREES_DEFAULT)
        self.loiter_trigger_duration = config_dict.get(
            "alert_loiter_trigger_duration_sec", LOITER_TRIGGER_DURATION_DEFAULT)
        self.loiter_aircraft_type = config_dict.get(
            "alert_loiter_aircraft_type", LOITER_AIRCRAFT_TYPE_DEFAULT)
        self.loiter_exclusions = config_dict.get("alert_loiter_exclusions", [])

    def exclude_sample(self, plat, plon):
        """ determines if a sample falls within an exclusion zone (ex: airport we expect aircraft to loiter) """
        for exclusion in self.loiter_exclusions:
            if exclusion["enabled"] is False:
                continue
            elat = exclusion["latitude"]
            elon = exclusion["longitude"]
            radius = exclusion["radius_meters"]
            _, _, proj_distance_m = self.geo.inv(
                elat, elon, plon, plat)
            if proj_distance_m < radius:
                return True
        return False

    def add_sample(self, hex_string, lat, lon, obs_time, track):
        """ adds a position and time sample for an aircraft obervation """
        if self.exclude_sample(lat, lon):
            return
        nav_record = self.nav_records.get(hex_string)
        if nav_record is None:
            nav_record = [[], [], [], [], False, None]
            self.nav_records[hex_string] = nav_record
            print(f"loiter_detector.add_sample() adding new hex: {hex_string}")
        nav_record[0].append(lat)
        nav_record[1].append(lon)
        nav_record[2].append(obs_time)
        nav_record[3].append(track)

        max_time_discontinutiy = 20
        if not is_continuous(nav_record[2], max_time_discontinutiy):
            nav_record = [[], [], [], [], False, None]

        self.nav_records[hex_string] = nav_record

    def check_for_loiter(self, hex_string):
        """ checks accumulated history for potential loitering aircraft
            this method either checks a specific hex_string or all active aircraft """
        # print("check_for_loiter")
        # print(hex_string)
        self.try_debug_print()
        # if we are passed no string, iterate through all and return all loitering records
        if hex_string is None:
            records = {}
            # pylint: disable=consider-iterating-dictionary
            # i can probably come up with a smarter implementation that ignoring the pylint complaint, but not right now...
            for key in self.nav_records.keys():
                # rec=self.nav_records[key]
                # hex_string=rec[0]
                # print("checking hex: %s" % key)
                rec = self.check_for_loiter(key)
                if rec[4]:
                    print(f"found loiter: {key}")
                    # records.append(rec)
                    records[key] = rec
            # pylint: enable=consider-iterating-dictionary
            return records

        nav_record = self.nav_records[hex_string]
        if nav_record[4]:
            # if we ever detect a loiter, maintain the loiter until we lose the track
            return nav_record
        max_time_discontinuity = 20
        in_loiter = is_loiter(nav_record[3], nav_record[2], max_time_discontinuity,
                              self.loiter_degrees, self.loiter_trigger_duration)
        nav_record[4] = in_loiter
        if in_loiter:
            # note the time we first detect the loiter
            nav_record[5] = nav_record[2][-1]
        self.nav_records[hex_string] = nav_record
        return nav_record

    def reset(self, hex_string):
        """ reset any track for the specified hex """
        nav_record = [[], [], [], [], False, None]
        self.nav_records[hex_string] = nav_record

    def purge_missing_hexes(self, active_hexes):
        """ occasionally called to purge track history for aircraft we no longer observe (no longer active) """
        # print("--------")
        # print(active_hexes)
        # print("--------")
        tracked_hexes = self.nav_records.keys()
        to_remove = []
        for hex_icao in tracked_hexes:
            if not hex_icao in active_hexes:
                print(
                    f"loiter_detector.purge_missing_keys() - purging {hex_icao}")
                # self.nav_records.pop(hex,None)
                to_remove.append(hex_icao)
        for hex_icao in to_remove:
            self.nav_records.pop(hex_icao, None)

    def debug_print(self):
        """ print debug info """
        list_of_hexes = self.nav_records.keys()
        print(f"loiter_detector.debug_print() @ {time.time()}")
        print("--------------------------------------")
        for hex_icao in list_of_hexes:
            print(
                f"{hex_icao} has {len(self.nav_records[hex_icao][0])} samples")
        print("--------------------------------------")

    def try_debug_print(self):
        """ only debug print at a given interval - skip if not enough time has passed """
        t = time.time()
        if t > self.debug_time + self.debug_interval_sec:
            self.debug_print()
            self.debug_time = t
