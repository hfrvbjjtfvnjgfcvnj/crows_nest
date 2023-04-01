
import os
import json
from datetime import datetime
import pyproj
import pushover

from loiter_detector import *

directions=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];

class Detector:
  def __init__(self,json_file,loiter_det):
    self.loiter_det = loiter_det;
    self.rules = self.load_definitions(json_file)
    self.geo=pyproj.Geod(ellps='WGS84')
    self.build_field_map();
    self.pending_intercepts={}
    self.call_count=0;
    self.notifiers=[];
    self.alert_types={};

  def load_data(self,json_file):
    if json_file is None:
      f=open(os.path.join(json_file));
    else:
      f=open(json_file);
    data=json.load(f);
    f.close();
    return data;

  def load_definitions(self,config_file):
    return self.load_data(config_file);

  def get_rules(self):
    return self.rules;

  def build_field_map(self):
    fields=self.rules['fields'];
    self.field_map={};
    i = 0;
    for field in fields:
      self.field_map[field] = i;
      i=i+1;
  
  def populate_alert_types(self,cursor):
    if len(self.alert_types) > 0:
      #only run once
      return
    print("Loading alert types from database...");
    cursor.execute('select * from alert_type');
    for ret in cursor:
      print("Setting alert type '%s' = '%d" % (ret[1],ret[0]));
      self.alert_types[ret[1]] = ret[0];

  def perform_detections(self,config,timestamp,conn,cursor):
    self.call_count=self.call_count+1;
    #a configurable 'frequency' for how often (as a number of calls), this function actually checks the DB
    #this may be desireable for low-ower/low-performance environments
    if (self.call_count % config.get("detector_every_n_updates",1) != 0):
      return;
    self.call_count = 0;

    self.populate_alert_types(cursor);

    new_notifications=[];

    #check for loitering aircraft
    if (config["alert_loiter"]): 
      loitering_data=self.loiter_det.check_for_loiter(None);
      loitering_hex_strings=loitering_data.keys();
      if (len(loitering_hex_strings) > 0):
        cursor.execute("CREATE OR REPLACE TABLE loiter_temp(hex CHAR(6) PRIMARY KEY);");
        for loiterer in loitering_hex_strings:
          cursor.execute("INSERT INTO loiter_temp(hex) VALUES (?) ON DUPLICATE KEY UPDATE hex=?",(loiterer.encode(),loiterer.encode()));
        conn.commit();
        rule=self.rules['loiter'];
        self.queue_notifications(config,cursor,new_notifications,rule['query'],rule['detected_title'],rule['position_title'],rule['alert_type_name']);

    #check for intercepting aircraft
    self.detect_intercepts(config,cursor,new_notifications);

    #check for general aircraft types
    if (len(config.get("alert_aircraft_type","")) > 0):
      rule=self.rules['type'];
      self.queue_notifications(config,cursor,new_notifications,rule['query']%config["alert_aircraft_type"],rule['detected_title']%config["alert_aircraft_type"],rule['position_title']%config["alert_aircraft_type"],rule['alert_type_name'])

    #check for military aircraft
    if (config["alert_military"]):
      rule=self.rules['military'];
      self.queue_notifications(config,cursor,new_notifications,rule['query'],rule['detected_title'],rule['position_title'],rule['alert_type_name']);
    
    #check for special aircraft
    if (config["alert_special"]):
      rule=self.rules['special'];
      self.queue_notifications(config,cursor,new_notifications,rule['query'],rule['detected_title'],rule['position_title'],rule['alert_type_name']);
    
    #check for know/suspected "spook" (recon/intel) aircraft
    if (config["alert_spook"]):
      rule=self.rules['spook'];
      self.queue_notifications(config,cursor,new_notifications,rule['query'],rule['detected_title'],rule['position_title'],rule['alert_type_name']);
    
    #check for "interesting" aircraft
    elif (config["alert_interesting"]): #'spook' is a subset of 'interesting', so don't do both notifications
      rule=self.rules['interesting'];
      self.queue_notifications(config,cursor,new_notifications,rule['query'],rule['detected_title'],rule['position_title'],rule['alert_type_name']);

    #check for government aircraft
    if (config["alert_government"]):
      rule=self.rules['government'];
      self.queue_notifications(config,cursor,new_notifications,rule['query'],rule['detected_title'],rule['position_title'],rule['alert_type_name']);
      
    for n in new_notifications:
      #print("NOTIFY: %s\n%s"%(n[0],n[2]));
      print(n);
      cursor.execute("insert into active_alerts(hex,first_seen,last_seen,alert_type) values(?,?,?,?) ON DUPLICATE KEY UPDATE last_seen=?, alert_type=? ;", (n[0],timestamp,timestamp,self.alert_types[n[3]],timestamp,self.alert_types[n[3]]));
      if (config["alert_notifications"]):
        self.do_notification(config,n);

  def find_active_alert(self,cursor,hex,alert_type_name):
    cursor.execute("select * from active_alerts join alert_type on active_alerts.alert_type=alert_type.id join active_aircraft on active_alerts.hex=active_aircraft.hex where active_alerts.hex=? and alert_type.id <= (select id from alert_type where name=?);",(hex,alert_type_name));
    return cursor.fetchall();

  def queue_notifications(self,config,cursor,new_notifications,query,detected_title,position_title,alert_type_name):
    #check for aircraft
    rows=[]
    cursor.execute(query);
    rows=cursor.fetchall();
    for aircraft in rows:
      hex=aircraft[0];
      lat=aircraft[3];
      lon=aircraft[4];
      distance=aircraft[5];

      #lookup any pre-existing active alert for this aircraft
      #this checks for any alert with type <= current alert type, allowing an escalation of notifications
      #if neede
      active_alert=self.find_active_alert(cursor,hex,alert_type_name);

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

  def detect_intercepts(self,config,cursor,new_notifications):
    positions=config.get("alert_eta_posititions", []);
    if len(positions) == 0:
      station_lat=config["station_latitude"];
      station_lon=config["station_longitude"];
      positions.append([station_lat,station_lon]);
    for pos in positions:
      self.detect_intercepts_at(config,cursor,new_notifications,pos[0],pos[1]);
  
  def detect_intercepts_at(self,config,cursor,new_notifications,eta_lat,eta_lon):
    rows=[]
    rule=self.rules['active'];
    cursor.execute(rule['query']);
    rows=cursor.fetchall();
    time_limit=600;
    time_step=15;
    alert_radius_m=config["alert_eta_radius_meters"];
    still_intercepting=[]
    for aircraft in rows:
      lat=aircraft[self.field_map['latitude']];
      lon=aircraft[self.field_map['longitude']];
      speed_knots=aircraft[self.field_map['speed']];
      track=aircraft[self.field_map['track']];
      icao_type_description=aircraft[self.field_map['description']];
      if (lat is None) or (lon is None) or (speed_knots is None) or (track is None):
        continue;

      if icao_type_description is not None:
        #get ICAO code (ex: L2J, H1T, etc) and extract first character as airframe type
        typecode=icao_type_description[0];
        typefilter=config.get("alert_aircraft_type","all");

        #if this type doesn't match the filter, skip the aircraft
        #"" and "all" match all codes
        if typefilter != "" and typefilter != "all" and typecode not in typefilter:
          continue;
      
      speed_meters_ps=speed_knots*0.514444; #1 knot ~= 0.514444 mps
      
      rule=self.rules['intercept'];
      for t in range(0,time_limit+1,time_step):
          #iterate over each time step in the detection range

          #estimate distance along track at each step
          proj_distance=speed_meters_ps*t;

          #compute estimated position at each step
          plon,plat,pbaz = self.geo.fwd(lon,lat,track,proj_distance);

          #compute distance to estimated position
          proj_bearing,proj_back_azimuth,proj_distance_m = self.geo.inv(eta_lon, eta_lat, plon, plat);

          if (proj_distance_m < alert_radius_m):
            hex=aircraft[self.field_map['hex']];
            
            #lookup a previous pending detection
            previous_det=self.pending_intercepts.get(hex);

            #config 'alert_eta_delay_filter_sec' represents how long an aircaft must be on an 'intercept' course before alerting
            #if 'alert_eta_delay_filter_sec' is configured for 0 delay, or the current intercepting detection time exceeds 'alert_eta_delay_filter_sec', queue the notification
            if (config["alert_eta_delay_filter_sec"] <= 0) or ((previous_det is not None) and (aircraft[self.field_map['time']] > previous_det[0] + config['alert_eta_delay_filter_sec'])):
              self.queue_notifications(config,cursor,new_notifications,rule['query']%aircraft[self.field_map['hex']],rule['detected_title'],rule['position_title'],rule['alert_type_name']);
            elif previous_det is None:
              #if there is no previous notification, add a pending one
              self.pending_intercepts[hex]=(aircraft[self.field_map['time']],rule['query']%aircraft[self.field_map['hex']],rule['detected_title'],rule['position_title'],rule['alert_type_name']);

            #keep track of the pending aircraft that are 'still' on intercept courses so we can cleanup pending_intercepts
            still_intercepting.append(hex);
            break;
    
    #cleanup pending_intercepts to remove any records of aircraft no longer on intercept courses
    keys = self.pending_intercepts.keys();
    purge=[]
    #build a purge list of keys not in the 'still_intercepting' list
    for key in keys:
      if key not in still_intercepting:
        purge.append(key);
    #remove keys in purge list
    for key in purge:
      self.pending_intercepts.pop(key);

  def do_notification(self,config,data):
    sound=None;
    priority=0;

    #notification data
    hex=data[0];
    title=data[1];
    aircraft=data[2];
    alert_type_name=data[3];

    #notification sound
    sound=self.note_sound(config,aircraft,alert_type_name);

    #print(sound);
    text=self.note_text(config,aircraft,alert_type_name)
    url=self.note_url(config,aircraft)
    
    for notifier in self.notifiers:
      notifier(config,title,text,priority,sound,url);

  def add_notifier(self,notifier_functor):
    self.notifiers.append(notifier_functor);

  def note_sound(self,config,aircraft,alert_type_name):
    if aircraft is None:
      return None;
  
    sound = None;
    
    #first apply rules for special alert type sounds
    keys=self.rules['sounds_alert_type'].keys();
    for key in keys:
      if alert_type_name == key:
        sound=self.rules['sounds_alert_type'][key];
        return sound

    icao_description=aircraft[self.field_map['description']];
    if icao_description is None:
      return None;
  
    #next apply rules for description (airframe) sounds
    keys=self.rules['sounds_airframe'].keys();
    for key in keys:
      if icao_description[0] == key:
        sound = self.rules['sounds_airframe'][icao_description[0]];
        return sound
      
    #next apply rules for description (engine) sounds
    keys=self.rules['sounds_engine'].keys();
    for key in keys:
      if icao_description[2] == key:
        self.rules['sounds_engine'][icao_description[2]];
  
    return None;

  def bearing_to_direction(self,bearing):
    while bearing < 0:
      bearing += 360;
    while bearing >= 360:
      bearing -= 360;
    index=int(bearing/22.5)
    return directions[index];

  def note_url(self,config,aircraft):
    aircraft_type=aircraft[self.field_map['icao_type_code']];
    url="https://globe.adsbexchange.com/aircraft_sil/%s.png"%(aircraft_type,);
    return url;

  def note_text(self,config,aircraft,alert_type):
    #print("--------------------")
    #print(aircraft);
    #print("--------------------")
    model='Unknown';
    time=datetime.fromtimestamp(aircraft[self.field_map['time']]).strftime('%Y-%m-%d %H:%M:%S');
    distance_miles=aircraft[self.field_map['distance']]/1609.34;
    bearing=aircraft[self.field_map['bearing']];
    bearing_str=self.bearing_to_direction(aircraft[self.field_map['bearing']]);
    hex=aircraft[self.field_map['hex']];
    lat=aircraft[self.field_map['latitude']];
    lon=aircraft[self.field_map['longitude']];
    registration=aircraft[self.field_map['registration']];
    operator=aircraft[self.field_map['registrant_name']];
    model=aircraft[self.field_map['icao_name']];
    icao_type_description=aircraft[self.field_map['description']];
    faa_type_aircraft=aircraft[self.field_map['faa_type_name']];
    comment=aircraft[self.field_map['comment']];
    #if we have a comment (ex: 'SPY PLANE')
    if comment is None:
      comment="";
    else:
      comment="Comment: %s\n"%comment;

    text="{}Operator: {}\nTime: {}\nModel: {}\nDistance: {:.2f} miles\nReg: {}\nBearing: {} ({})\nHex Code: {}\nLatitude: {}\nLongitude: {}\nICAO Type: {}\nFAA Type: {}\n{}\n{}\n{}".format(
          comment,
          operator,
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
