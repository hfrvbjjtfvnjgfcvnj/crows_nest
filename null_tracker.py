""" 'null' tracker that doesn't do anything """


class Tracker:
    """ The goggles... they do nossing """

    def __init__(self, _):
        print("null_tracker - Tracker() - Initialized")

    def track_alert_aircraft(self, list_of_aircraft, field_map):
        """ does nothing """
