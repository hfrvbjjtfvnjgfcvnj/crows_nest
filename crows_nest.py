import inotify.adapters;
import os
import json
import mariadb
import pyproj
from datetime import datetime
import time
from queue import Queue
import shutil
import importlib.util
from threading import Thread

from loiter_detector import *
from detector import Detector

directions=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
config={}
old_data={}
inotify_queue=Queue()
temp_dir='/tmp'
loiter_det=loiter_detector();
det=Detector('detector.json',loiter_det);
dump1090_time=time.time();

def load_configuration():
  global config;
  dirname = os.path.dirname(__file__)
  filename = os.path.join(dirname, 'config.json')
  f=open(filename);
  config=json.load(f);
  f.close();
  print(config);
  loiter_det.configure(config);

def load_data(json_file):
  if json_file is None:
    f=open(os.path.join(config["dump1090_aircraft_path"],config["dump1090_aircraft_name"]));
  else:
    f=open(json_file);
  data=json.load(f);
  f.close();
  return data;

def get_val(a_dictionary,a_key):
  if a_key in a_dictionary: #a_dictionary.has_key(a_key):
    return a_dictionary[a_key];
  return None;

def clear_expired():
  #delete any alerts older from aircraft that are no longer being seen and updating
  cursor.execute("delete from active_alerts where last_seen<? ",(dump1090_time-config["alert_expire_seconds"],));
  
  #delete any expired "active" aircraft that are no longer being seen and updating)
  cursor.execute("DELETE FROM active_aircraft WHERE time<? ",(dump1090_time-config["aircraft_expire_seconds"],));
  
  #delete any track histories for any aircraft no longer "active"
  cursor.execute("DELETE FROM active_aircraft_history WHERE NOT EXISTS(SELECT NULL FROM active_aircraft where active_aircraft.hex = active_aircraft_history.hex);");
  
  conn.commit();

  #purge records from the loiter detector when aircraft drop off the active list
  cursor.execute("SELECT hex FROM active_aircraft;");
  rows=cursor.fetchall();
  list_of_hexes=[]
  for row in rows:
    list_of_hexes.append(row[0]);
  loiter_det.purge_missing_hexes(list_of_hexes);
  conn.commit();

def commit_to_db(timestamp,aircraft):
  global dump1090_time;
  
  station_lat=config["station_latitude"];
  station_lon=config["station_longitude"];
  icao=get_val(aircraft,'hex')[:6];
  squawk=get_val(aircraft,'squawk');
  flight=get_val(aircraft,'flight');
  lat=get_val(aircraft,'lat');
  lon=get_val(aircraft,'lon');
  nucp=get_val(aircraft,'nucp');
  seen_pos=get_val(aircraft,'seen_pos');
  altitude=get_val(aircraft,'altitude');
  if type(0) != type(altitude):
    altitude=0;
  vert_rate=get_val(aircraft,'vert_rate');
  track=get_val(aircraft,'track');
  speed=get_val(aircraft,'speed');
  messages=get_val(aircraft,'messages');
  seen=get_val(aircraft,'seen');
  rssi=get_val(aircraft,'rssi');
 
  #record incoming sample times - there seems to be some drift between dump1090 and crows_nest
  #maybe dump1090 isn't using system time and is tracking it's own time somehow?
  dump1090_time=timestamp;

  #bulk-log data if configured to do so
  if config.get("data_log_enabled",False):
    cursor.execute("INSERT INTO data_log(time,hex,flight,lat,lon,altitude,vert_rate,track,speed,seen,seen_pos,rssi,nucp,squawk) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (timestamp,icao.encode(),flight,lat,lon,altitude,vert_rate,track,speed,seen,seen_pos,rssi,nucp,squawk));
  
  #if lat is not None and lon is not None and rssi is not None and altitude is not None:
  bearing=None;distance_m=None;
  if lat is not None and lon is not None and rssi is not None and altitude is not None:
    bearing,back_azimuth,distance_m = geo.inv(station_lon, station_lat, lon, lat)
    bearing=int(bearing);
    while bearing < 0:
      bearing = bearing+360;
    while bearing >=360:
      bearing = bearing-360;
    cursor.execute("INSERT INTO signal_reception(time,bearing,dist,alt,rssi) values (?,?,?,?,?)",(timestamp,bearing,distance_m,altitude,rssi));
  if (lat is None) and (lon is None):
    cursor.execute("INSERT INTO active_aircraft(hex, time, first_det_time, seen_pos, latitude, longitude, distance,bearing,speed,track,altitude) values (?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE time=?",(icao.encode(),timestamp,timestamp,seen_pos,lat,lon,distance_m,bearing,speed,track,altitude,timestamp));
  else:
    cursor.execute("INSERT INTO active_aircraft       (hex, time, first_det_time, seen_pos, latitude, longitude, distance,bearing,speed,track,altitude) values (?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE time=?, seen_pos=?, latitude=?, longitude=?, distance=?, bearing=?, speed=?, track=?, altitude=?",(icao.encode(),timestamp,timestamp,seen_pos,lat,lon,distance_m,bearing,speed,track,altitude,timestamp,seen_pos,lat,lon,distance_m,bearing,speed,track,altitude));
    cursor.execute("INSERT INTO active_aircraft_history(hex, time, seen_pos, latitude, longitude, distance,bearing,speed,track,altitude) values (?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE time=?, seen_pos=?, latitude=?, longitude=?, distance=?, bearing=?, speed=?, track=?, altitude=?",(icao.encode(),timestamp,seen_pos,lat,lon,distance_m,bearing,speed,track,altitude,timestamp,seen_pos,lat,lon,distance_m,bearing,speed,track,altitude));
    loiter_det.add_sample(icao,lat,lon,timestamp,track);
  cursor.execute("INSERT INTO detected_aircraft(hex, time, seen_pos) values (?,?,?) ON DUPLICATE KEY UPDATE time=?, seen_pos=?",(icao.encode(),timestamp,seen_pos,timestamp,seen_pos));
  
  cursor.execute("UPDATE active_alerts SET last_seen=? where hex=?", (timestamp,icao));
  conn.commit();

def update_from_json(json_file):
  global old_data;
  data=load_data(json_file);
  if (data == old_data):
    #it is possible we get multiple notifies on the same file due to delays caused by notifications
    #this is because we missed an update to the aircraft file and are reading the same file twice
    #we already lost the data, don't try to log what we have more than once
    return;
  old_data=data;
  timestamp=data['now'];
  aircraft_list=data['aircraft'];
  #print("time.time() %f \n dump1090_time: %f \n diff: %f" % (time.time(), timestamp, (time.time()-timestamp)));

  if (abs(time.time()-timestamp) > 10):
    print("ERROR: TIME DRIFT. EXITING TO PRESERVE LOGS")
    exit(1);

  for aircraft in aircraft_list:
    commit_to_db(timestamp, aircraft);
  clear_expired(); 
  det.perform_detections(config,timestamp,conn,cursor);
  conn.commit();

def _main_inotify():
  i = inotify.adapters.Inotify();
  i.add_watch(config["dump1090_aircraft_path"]);
  inpath=os.path.join(config["dump1090_aircraft_path"],config["dump1090_aircraft_name"]);
  tmppath="/tmp/cna.json"

  for event in i.event_gen(yield_nones=False):
    (_,type_names,path,filename)=event;
    if (config["dump1090_aircraft_name"] == filename) and ('IN_MOVED_TO' in type_names):
      shutil.copyfile(inpath,tmppath);
      update_from_json(tmppath);

def test2():
    update_from_json("aircraft.json");

load_configuration();

notifier_config=config.get('notifiers',None);
for notifier_def in notifier_config:
  spec = importlib.util.spec_from_file_location(notifier_def['name'],notifier_def['file']);
  module = importlib.util.module_from_spec(spec);
  spec.loader.exec_module(module);
  det.add_notifier(module.NotifierFunctor());


ag_sbs = {};
ag_time = time.time();

conn=mariadb.connect(
          user=config["db_username"],
          password=config["db_password"],
          host=config["db_host"],
          port=config["db_port"],
          database=config["db_database_name"]
          );
#conn.autocommit = False
conn.autocommit = True
cursor=conn.cursor();

geo=pyproj.Geod(ellps='WGS84')



if __name__ == '__main__':
  _main_inotify();
  #test2();

