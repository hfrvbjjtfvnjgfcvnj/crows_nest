from loiter import *

class loiter_detector:
  def __init__(self) -> None:
    self.nav_records={}

  def add_sample(self,hex_string,lat,lon,time,track):
    nav_record=self.nav_records.get(hex_string);
    if nav_record is None:
      nav_record=[[],[],[],[],False];
      self.nav_records[hex_string] = nav_record;
    nav_record[0].append(lat);
    nav_record[1].append(lon);
    nav_record[2].append(time);
    nav_record[3].append(track);

    max_time_discontinutiy=20;
    if not is_continuous(nav_record[2],max_time_discontinutiy):
      nav_record=[[],[],[],[],False];
    
    self.nav_records[hex_string] = nav_record;

  def check_for_loiter(self,hex_string):
    #print("check_for_loiter")
    #print(hex_string);
    #if we are passed no string, iterate through all and return all loitering records
    if hex_string is None:
        records=[]
        for key in self.nav_records.keys():
            #rec=self.nav_records[key];
            #hex_string=rec[0];
            #print("checking hex: %s" % key);
            rec=self.check_for_loiter(key);
            if (rec[4]):
                print("found loiter: %s" % key);
                records.append(rec)
        return records;

    nav_record=self.nav_records[hex_string];
    if (nav_record[4]):
      #if we ever detect a loiter, maintain the loiter until we lose the track
      return nav_record;
    max_time_discontinutiy=20;
    in_loiter=is_loiter(nav_record[3],nav_record[2],max_time_discontinutiy);
    nav_record[4]=in_loiter;
    self.nav_records[hex_string]=nav_record;
    return nav_record

  def reset(self,hex_string):
    nav_record=[[],[],[],[],False];
    self.nav_records[hex_string] = nav_record;

  def purge_missing_hexes(self,list_of_hexes):
    for hex in list_of_hexes:
      self.nav_records.pop(hex,None);
