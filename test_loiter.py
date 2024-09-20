""" loiter test code """
import csv
import debugpy
import matplotlib.pyplot as plt
from loiter import is_loiter, is_continuous

from loiter_detector import LOITER_DEGREES_DEFAULT, LOITER_TRIGGER_DURATION_DEFAULT

debugpy.listen(5678)
print("Waiting for debugger to attach")
debugpy.wait_for_client()

# pylint: disable=bare-except
# pylint: disable=invalid-name
# pylint: disable=consider-using-enumerate


def extract_vector(db_records, column_names, name_to_extract):
    """ extracts a column from a set of records into a vector """
    column = []
    try:
        index = column_names.index(name_to_extract)
    except:
        return None
    for record in db_records:
        column.append(record[index])
    return column


def convert_vector(vector):
    """ convert vector data to float """
    float_vector = []
    for v in vector:
        try:
            float_vector.append(float(v))
        except:
            float_vector.append(None)
    return float_vector


file = 'tracks_0.csv'
records = []
key = None
with open(file, newline='', encoding="utf-8") as csvfile:
    spamreader = csv.reader(csvfile)
    for row in spamreader:
        if key is None:
            key = row
        else:
            records.append(row)

time = convert_vector(extract_vector(records, key, 'time'))
lat = convert_vector(extract_vector(records, key, 'lat'))
lon = convert_vector(extract_vector(records, key, 'lon'))
track = convert_vector(extract_vector(records, key, 'track'))

time_0 = []
track_0 = []
start = 0
max_time_discontinuity = 20
max_track_discontinuity = 20
# for t in time:
for i in range(0, len(time)):
    time_0 = time[start:i]
    track_0 = track[start:i]
    if (time[i] is None) or (track[i] is None):
        start = i
    # and is_continuous(track_0,max_track_discontinuity):
    elif is_continuous(time_0, max_time_discontinuity):
        result = is_loiter(track_0, time_0, max_time_discontinuity,
                           LOITER_DEGREES_DEFAULT, LOITER_TRIGGER_DURATION_DEFAULT)
        if result:
            print(f"loiter: {start}->{i}")
            plt.plot(lon[start:i], lat[start:i])
            plt.show()
            start = i
        # else:
        #  print("exanding search...")
    else:
        print(f"discontinuity @ {i}")
        start = i
