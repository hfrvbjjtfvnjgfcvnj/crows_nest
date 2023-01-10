import inotify.adapters;
import os
import json
import mariadb
import sys
import pyproj
import socket
from datetime import datetime
import time
import pushover
from queue import Queue
import shutil
import tempfile
from threading import Thread

directions=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
alert_types={}
config={}
old_data={}
inotify_queue=Queue()
temp_dir=tempfile.mkdtemp();

def load_configuration():
  global config;
  dirname = os.path.dirname(__file__)
  filename = os.path.join(dirname, 'config.json')
  f=open(filename);
  config=json.load(f);
  f.close();
  print(config);

def populate_alert_types(cursor):
  global alert_types;
  print("Loading alert types from database...");
  cursor.execute('select * from alert_type');
  for ret in cursor:
    print("Setting alert type '%s' = '%d" % (ret[1],ret[0]));
    alert_types[ret[1]] = ret[0];

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

def pushover_notify(title,msg_text,priority,sound,url):
  po=pushover.Pushover(config["pushover_api_key"]);
  po.user(config["pushover_user_key"]);
  msg=po.msg(msg_text);
  msg.set('title',title);
  msg.set('priority',priority);
  if sound is not None:
    msg.set('sound', sound);
  if url is not None:
    msg.set('url', url);
  return po.send(msg);

def find_active_alert(hex):
  #cursor.execute("select * from active_alerts where hex=?",(hex,));
  cursor.execute("select * from active_alerts join active_aircraft on active_alerts.hex=active_aircraft.hex where active_alerts.hex=?",(hex,));
  return cursor.fetchall();

def has_active_position(hex):
  cursor.execute("select hex from active_aircraft where hex=? AND seen_pos IS NOT NULL",(hex,));
  for icao in cursor:
    return True;
  return False;

def bearing_to_direction(bearing):
  while bearing < 0:
    bearing += 360;
  while bearing >= 360:
    bearing -= 360;
  index=int(bearing/22.5)
  return directions[index];

def note_url(aircraft):
  aircraft_type=aircraft[9];
  url="https://globe.adsbexchange.com/aircraft_sil/%s.png"%(aircraft_type,);
  return url;

def note_text(aircraft):
  #print("--------------------")
  #print(aircraft);
  #print("--------------------")
  model='Unknown';
  time=datetime.fromtimestamp(aircraft[1]).strftime('%Y-%m-%d %H:%M:%S');
  distance_miles=aircraft[5]/1609.34;
  bearing=aircraft[6];
  bearing_str=bearing_to_direction(aircraft[6]);
  hex=aircraft[0];
  lat=aircraft[3];
  lon=aircraft[4];
  registration='Unknown'
  if (len(aircraft)>=18):
    model=aircraft[10];
    registration=aircraft[8];
    icao_type_description=aircraft[12];
    faa_type_aircraft=aircraft[17];

  text="Time: {}\nModel: {}\nDistance: {:.2f} miles\nReg: {}\nBearing: {} ({})\nHex Code: {}\nLatitude: {}\nLongitude: {}\nICAO Type: {}\nFAA Type: {}\n{}\n{}\n{}".format(
        time,
        model,
        distance_miles,
        registration,
        bearing,
        bearing_str,
        hex,
        lat,
        lon,
        icao_type_description,
        faa_type_aircraft,
        config["dump1090_local_url"],
        "https://globe.adsbexchange.com/?feed=%s" % (config["adsb_exchange_feed_code"],),
        "https://globe.adsbexchange.com/?icao=%s" % (hex,));
  return text

def note_sound(aircraft):
  if aircraft is None:
    return None;
  icao_description=aircraft[12];
  if icao_description is None:
    return None;
  if ("H" == icao_description[0]) or ("T" == icao_description[0]):
    #helicopter or tilt-rotor
    return 'chopper';
  if ("J" == icao_description[2]):
    return "fastmover";
  if ("T" == icao_description[2]):
    return "turbo_prop";
  if ("P" == icao_description[2]):
    return "pison_engine";
  return None;

def do_notification(data):
  sound=None;
  priority=0;
  #pushover_notify(n[1],n[2],0);
  #if data[3] == 'military':
  #  sound='fastmover';
  #  #priority=-1;
  #if data[3] == 'government':
  #  sound='chopper';
  #  #priority=0;
  sound=note_sound(data[2]);
  text=note_text(data[2])
  url=note_url(data[2])
  pushover_notify(data[1],text,priority,sound,url);

def queue_notifications(new_notifications,query,detected_title,position_title,alert_type_name):
  #check for aircraft
  rows=[]
  cursor.execute(query);
  rows=cursor.fetchall();
  for aircraft in rows:
    hex=aircraft[0];
    lat=aircraft[3];
    lon=aircraft[4];
    distance=aircraft[5];
    type_code=None;
    model=None;
    type_description=None;

    #lookup any pre-existing active alert for this aircraft
    active_alert=find_active_alert(hex);

    #is this a new detection without an existing alert?
    is_new_alert=(len(active_alert)==0);

    #does this detection have a position?
    has_position=((lat is not None) and (lon is not None) and (distance is not None));

    if is_new_alert:
      if has_position:
        if (config["alert_without_position"]) or (distance < config["alert_radius_meters"]):
          new_notifications.append((aircraft[0],position_title,aircraft,alert_type_name));
      elif config["alert_without_position"]:   #should alert detections with no position data
        new_notifications.append((aircraft[0],detected_title,aircraft,alert_type_name));
    elif has_position: #an alert alread exists on this aircraft
      #we only notify it if we do not already have a position in the previous alert
      alert_has_pos=((active_alert[0][7] is not None) and (active_alert[0][8] is not None));
      if not alert_has_pos:
        new_notifications.append((aircraft[0],position_title,aircraft,alert_type_name));

def perform_detections(timestamp, cursor):
  new_notifications=[];
  
  #check for military aircraft
  if (config["alert_military"]):
    queue_notifications(new_notifications,
      #"select * from (active_aircraft left join known_military_aircraft on active_aircraft.hex=known_military_aircraft.hex) where active_aircraft.hex>='ADF7C8' and active_aircraft.hex<='AFFFFF'",
      #"select * from (((active_aircraft left join tar1090_db on active_aircraft.hex=tar1090_db.hex) join icao_type_descriptions on tar1090_db.icao_type_code=icao_type_descriptions.type) ) join faa_lookup_table on active_aircraft.hex=faa_lookup_table.mode_s_hex_code left join faa_aircraft_type on faa_lookup_table.type_aircraft=faa_aircraft_type.id where active_aircraft.hex>='ADF7C8' and active_aircraft.hex<='AFFFFF';",
      "select * from (((active_aircraft left join tar1090_db on active_aircraft.hex=tar1090_db.hex) left join icao_type_descriptions on tar1090_db.icao_type_code=icao_type_descriptions.type) ) left join faa_lookup_table on active_aircraft.hex=faa_lookup_table.mode_s_hex_code left join faa_aircraft_type on faa_lookup_table.type_aircraft=faa_aircraft_type.id where active_aircraft.hex>='ADF7C8' and active_aircraft.hex<='AFFFFF';",
      "Military Aircraft Detected",
      "Military Aircraft Position Acquired",
      'military');
  
  #check for special aircraft
  if (config["alert_special"]):
    queue_notifications(new_notifications,
      "select * from (((active_aircraft left join tar1090_db on active_aircraft.hex=tar1090_db.hex) left join icao_type_descriptions on tar1090_db.icao_type_code=icao_type_descriptions.type) ) left join faa_lookup_table on active_aircraft.hex=faa_lookup_table.mode_s_hex_code left join faa_aircraft_type on faa_lookup_table.type_aircraft=faa_aircraft_type.id join special_aircraft on active_aircraft.hex=special_aircraft.hex;",
      "Special Alert Aircraft Detected",
      "Special Alert Aircraft Position Acquired",
      'special');
    

  #check for government aircraft
  if (config["alert_government"]):
    queue_notifications(new_notifications,
      "select * from (((active_aircraft left join tar1090_db on active_aircraft.hex=tar1090_db.hex) left join icao_type_descriptions on tar1090_db.icao_type_code=icao_type_descriptions.type) ) left join faa_lookup_table on active_aircraft.hex=faa_lookup_table.mode_s_hex_code left join faa_aircraft_type on faa_lookup_table.type_aircraft=faa_aircraft_type.id join gov_records on active_aircraft.hex=gov_records.hex;",
      "Government Aircraft Detected",
      "Government Aircraft Position Acquired",
      'government');
    
  for n in new_notifications:
    #print("NOTIFY: %s\n%s"%(n[0],n[2]));
    cursor.execute('insert into active_alerts(hex,first_seen,last_seen,alert_type) values(?,?,?,?) ON DUPLICATE KEY UPDATE last_seen=?', (n[0],timestamp,timestamp,alert_types[n[3]],timestamp));
    if (config["alert_notifications"]):
      do_notification(n);

def clear_old_alerts():
  cursor.execute("delete from active_alerts where last_seen<? returning *",(time.time()-config["alert_expire_seconds"],));
  for row in cursor:
    print("clearing alert: %s" % row[0]);

def commit_to_db(timestamp,aircraft):
  #print(timestamp);
  #print(aircraft);
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
  vert_rate=get_val(aircraft,'vert_rate');
  track=get_val(aircraft,'track');
  speed=get_val(aircraft,'speed');
  messages=get_val(aircraft,'messages');
  seen=get_val(aircraft,'seen');
  rssi=get_val(aircraft,'rssi');
  #print('|%s|' % icao);
  #print(squawk);
  #print(flight);
  #print(lat);
  #print(lon);
  #print(nucp);
  #print(seen_pos);
  #print(altitude);
  #print(vert_rate);
  #print(track);
  #print(speed);
  #print(messages);
  #print(seen);
  #print(rssi);
  
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
    cursor.execute("INSERT INTO active_aircraft(hex, time, seen_pos, latitude, longitude, distance,bearing) values (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE time=?",(icao.encode(),timestamp,seen_pos,lat,lon,distance_m,bearing,timestamp));
  else:
    cursor.execute("INSERT INTO active_aircraft(hex, time, seen_pos, latitude, longitude, distance,bearing) values (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE time=?, seen_pos=?, latitude=?, longitude=?, distance=?, bearing=?",(icao.encode(),timestamp,seen_pos,lat,lon,distance_m,bearing,timestamp,seen_pos,lat,lon,distance_m,bearing));
  cursor.execute("INSERT INTO detected_aircraft(hex, time, seen_pos) values (?,?,?) ON DUPLICATE KEY UPDATE time=?, seen_pos=?",(icao.encode(),timestamp,seen_pos,timestamp,seen_pos));
  

  cursor.execute("DELETE FROM active_aircraft WHERE time<?",(time.time()-config["aircraft_expire_seconds"],));
  cursor.execute("UPDATE active_alerts SET last_seen=? where hex=?", (timestamp,icao));

  conn.commit();

def update_from_json(json_file):
  global old_data;
  station_lat=config["station_latitude"];
  station_lon=config["station_longitude"];
  data=load_data(json_file);
  if (data == old_data):
    #it is possible we get multiple notifies on the same file due to delays caused by notifications
    #this is because we missed an update to the aircraft file and are reading the same file twice
    #we already lost the data, don't try to log what we have more than once
    return;
  old_data=data;
  timestamp=data['now'];
  aircraft_list=data['aircraft'];
  for aircraft in aircraft_list:
    commit_to_db(timestamp, aircraft);
  clear_old_alerts(); 
  perform_detections(timestamp,cursor);
  conn.commit();

def _main_inotify():
  i = inotify.adapters.Inotify();
  i.add_watch(config["dump1090_aircraft_path"]);

  for event in i.event_gen(yield_nones=False):
    (_,type_names,path,filename)=event;
    if (config["dump1090_aircraft_name"] == filename) and ('IN_MOVED_TO' in type_names):
      update_from_json();

def _thread_inotify_queue_reader():
  while True:
    temp=inotify_queue.get();
    update_from_json(temp);
    os.remove(temp);

def _main_inotify_queue():
  thread = Thread(target=_thread_inotify_queue_reader);
  thread.start();
  i = inotify.adapters.Inotify();
  i.add_watch(config["dump1090_aircraft_path"]);

  for event in i.event_gen(yield_nones=False):
    (_,type_names,path,filename)=event;
    if (config["dump1090_aircraft_name"] == filename) and ('IN_MOVED_TO' in type_names):
      #update_from_json();
      inpath=os.path.join(config["dump1090_aircraft_path"],config["dump1090_aircraft_name"]);
      outpath=os.path.join(temp_dir,str(time.time()));
      shutil.copyfile(inpath,outpath);
      inotify_queue.put(outpath);

def test():
    hex='ae63fd'
    #lookup any pre-existing active alert for this aircraft
    active_alert=find_active_alert(hex);
    print("active_alert");
    print(active_alert);

    #is this a new detection without an existing alert?
    is_new_alert=(len(active_alert)==0);
    print("len(active_alert)");
    print(len(active_alert));
    print("is_new_alert");
    print(is_new_alert);

    alert_has_pos=((active_alert[0][7] is not None) and (active_alert[0][8] is not None));
    print("active_alert[0]")
    print(active_alert[0])
    print("active_alert[0][7]")
    print(active_alert[0][7])
    print("active_alert[0][8]")
    print(active_alert[0][8])
    print("alert_has_pos");
    print(alert_has_pos);

def test2():
    update_from_json("aircraft.json");

load_configuration();

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

populate_alert_types(cursor);

geo=pyproj.Geod(ellps='WGS84')



if __name__ == '__main__':
  #_main();
  #_main_inotify();
  _main_inotify_queue();
  #test();
  #test2();

