""" new loiter test case """

import csv
import matplotlib.pyplot as plt
from loiter import unwrap_track

# pylint: disable=invalid-name

file = 'aircraft_track_1.csv'
records = []
key = None
with open(file, newline='', encoding="utf-8") as csvfile:
    spamreader = csv.reader(csvfile)
    for row in spamreader:
        if key is None:
            key = row
        else:
            records.append(row)

track = []
for record in records:
    track.append(int(record[0]))

print(track)

plt.plot(track)
# plt.show()

unwrapped = unwrap_track(track)
plt.plot(unwrapped)
plt.show()

print(abs(max(unwrapped)-min(unwrapped)))
