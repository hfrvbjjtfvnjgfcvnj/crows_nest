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

time_0=[]
track_0=[]
start=0;
max_time_discontinuity=20;
max_track_discontinuity=20;
#for t in time:
for i in range(0,len(time)):
  time_0=time[start:i];
  track_0=track[start:i];
  if (time[i] is None) or (track[i] is None):
    start=i;
  elif is_continuous(time_0,max_time_discontinuity):# and is_continuous(track_0,max_track_discontinuity):
    result=is_loiter(track_0,time_0,max_time_discontinuity);
    if result:
      print("loiter: %d->%d" % (start,i));
      plt.plot(lon[start:i],lat[start:i]);
      plt.show();
      start=i;
    #else:
    #  print("exanding search...")
  else:
    print("discontinuity @ %d" % i);
    start=i;

