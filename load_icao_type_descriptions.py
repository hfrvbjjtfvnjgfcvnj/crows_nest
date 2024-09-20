""" Converts icao aircraft type codes from JSON to CSV for DB import """

import json


def load_file(path_to_file):
    """ load data from JSON """
    f = open(path_to_file, encoding="utf-8")
    data = json.load(f)
    f.close()
    return data


def load_data():
    """ load data from JSON and print to console """
    path_to_file = "icao_aircraft_types.json"
    data = load_file(path_to_file)
    for type_name in data:
        value = data[type_name]
        description = value["desc"]
        print(f"{type_name},{description}")


def __test():
    data = load_file("icao_aircraft_types.json")
    print(data)


if __name__ == '__main__':
    # __test()
    load_data()
