from loiter import *
import time
import pyproj

loiter_degrees_DEFAULT=360;
loiter_trigger_duration_DEFAULT=9999999;
loiter_aircraft_type_DEFAULT="*";

class loiter_detector:
  def __init__(self) -> None:
    self.nav_records={}
    self.debug=True
    self.debug_time=time.time()
    self.debug_interval_sec=60;
    self.loiter_degrees = loiter_degrees_DEFAULT;
    self.loiter_trigger_duration = loiter_trigger_duration_DEFAULT;
    self.loiter_aircraft_type = loiter_aircraft_type_DEFAULT;
    self.geo=pyproj.Geod(ellps='WGS84')

  def configure(self, config_dict):
    self.loiter_degrees=config_dict.get("alert_loiter_degrees", loiter_degrees_DEFAULT);
    self.loiter_trigger_duration=config_dict.get("alert_loiter_trigger_duration_sec", loiter_trigger_duration_DEFAULT);
    self.loiter_aircraft_type=config_dict.get("alert_loiter_aircraft_type", loiter_aircraft_type_DEFAULT);
    self.loiter_exclusions=config_dict.get("alert_loiter_exclusions",[]);

  def exclude_sample(self,plat,plon):
    for exclusion in self.loiter_exclusions:
      if exclusion["enabled"] == False:
        continue;
      elat=exclusion["latitude"];
      elon=exclusion["longitude"];
      radius=exclusion["radius_meters"];
      proj_bearing,proj_back_azimuth,proj_distance_m = self.geo.inv(elat, elon, plon, plat);
      if proj_distance_m < radius:
        return True
    return False

  def add_sample(self,hex_string,lat,lon,time,track):
    if self.exclude_sample(lat,lon):
      return
    nav_record=self.nav_records.get(hex_string);
    if nav_record is None:
      nav_record=[[],[],[],[],False,None];
      self.nav_records[hex_string] = nav_record;
      print("loiter_detector.add_sample() adding new hex: %s" % hex_string);
    nav_record[0].append(lat);
    nav_record[1].append(lon);
    nav_record[2].append(time);
    nav_record[3].append(track);

    max_time_discontinutiy=20;
    if not is_continuous(nav_record[2],max_time_discontinutiy):
      nav_record=[[],[],[],[],False,None];
    
    self.nav_records[hex_string] = nav_record;

  def check_for_loiter(self,hex_string):
    #print("check_for_loiter")
    #print(hex_string);
    self.try_debug_print();
    #if we are passed no string, iterate through all and return all loitering records
    if hex_string is None:
        records={}
        for key in self.nav_records.keys():
            #rec=self.nav_records[key];
            #hex_string=rec[0];
            #print("checking hex: %s" % key);
            rec=self.check_for_loiter(key);
            if (rec[4]):
                print("found loiter: %s" % key);
                #records.append(rec)
                records[key]=rec;
        return records;

    nav_record=self.nav_records[hex_string];
    if (nav_record[4]):
      #if we ever detect a loiter, maintain the loiter until we lose the track
      return nav_record;
    max_time_discontinuity=20;
    in_loiter=is_loiter(nav_record[3],nav_record[2],max_time_discontinuity,self.loiter_degrees,self.loiter_trigger_duration);
    nav_record[4]=in_loiter;
    if in_loiter:
      #note the time we first detect the loiter
      nav_record[5]=nav_record[2][-1];
    self.nav_records[hex_string]=nav_record;
    return nav_record

  def reset(self,hex_string):
    nav_record=[[],[],[],[],False,None];
    self.nav_records[hex_string] = nav_record;

  def purge_missing_hexes(self,active_hexes):
    #print("--------");
    #print(active_hexes);
    #print("--------");
    tracked_hexes=self.nav_records.keys();
    to_remove=[]
    for hex in tracked_hexes:
      if not hex in active_hexes:
        print("loiter_detector.purge_missing_keys() - purging %s" % hex);
        #self.nav_records.pop(hex,None);
        to_remove.append(hex);
    for hex in to_remove:
      self.nav_records.pop(hex,None);

  def debug_print(self):
    list_of_hexes=self.nav_records.keys();
    print("loiter_detector.debug_print() @ %f" % (time.time()));
    print("--------------------------------------");
    for hex in list_of_hexes:
      print("%s has %d samples" % (hex, len(self.nav_records[hex][0])));
    print("--------------------------------------");

  def try_debug_print(self):
    t=time.time();
    if (t > self.debug_time + self.debug_interval_sec):
      self.debug_print();
      self.debug_time=t;


