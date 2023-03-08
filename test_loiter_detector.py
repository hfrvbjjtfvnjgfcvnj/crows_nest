import debugpy
import matplotlib.pyplot as plt

debugpy.listen(5678);
print("Waiting for debugger to attach");
debugpy.wait_for_client();

def extract_vector(records,column_names,name_to_extract):
  column=[]
  try:
    i=column_names.index(name_to_extract);
  except:
    return None
  for record in records:
    column.append(record[i]);
  return column

def convert_vector(vector):
  float_vector=[]
  for v in vector:
    try:
      float_vector.append(float(v))
    except:
      float_vector.append(None);
  return float_vector

file='tracks_0.csv'
import csv
from loiter import *
records=[]
key=None
with open(file, newline='') as csvfile:
  spamreader = csv.reader(csvfile)
  for row in spamreader:
    if key is None:
      key=row;
    else:
      records.append(row);
      
time=convert_vector(extract_vector(records,key,'time'))
lat=convert_vector(extract_vector(records,key,'lat'))
lon=convert_vector(extract_vector(records,key,'lon'))
track=convert_vector(extract_vector(records,key,'track'))

from loiter_detector import *

ld=loiter_detector();

in_loiter = False;
for i in range(0,len(time)):
  ld.add_sample('test', lat[i], lon[i], time[i], track[i]);
  loiter_status=ld.check_for_loiter('test');
  now_in_loiter=loiter_status[4];
  if (in_loiter != now_in_loiter):
    in_loiter=now_in_loiter;
    if in_loiter:
      plt.plot(loiter_status[1][0:i],loiter_status[0][0:i]);
      plt.show();
      print("loiter found %d" % i);
      ld.reset('test');
    else:
      print("loiter completed");