import json
import os
import sys
import mariadb

def load_file(path_to_file):
  f=open(path_to_file);
  data=json.load(f);
  f.close();
  return data;

def load_data():
  path_to_file="icao_aircraft_types.json";
  data=load_file(path_to_file);
  for type_name in data:
    value=data[type_name];
    description=value["desc"];
    print("%s,%s" % (type_name,description));

def __test():
  data=load_file("icao_aircraft_types.json");
  print(data);

if __name__ == '__main__':
  #__test();
  load_data();
