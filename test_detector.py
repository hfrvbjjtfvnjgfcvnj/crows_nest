""" test example for detector rules """
import debugpy

from detector import Detector
from loiter_detector import LoiterDetector

debugpy.listen(5678)
print("Waiting for debugger to attach")
debugpy.wait_for_client()

# rules = load_definitions("./detector.json")
det = Detector("./detector.json", LoiterDetector())
rules = det.get_rules()
print(rules)
fields = rules['fields']
print(fields)
print(fields[1])
