import debugpy

from detector import *

debugpy.listen(5678);
print("Waiting for debugger to attach");
debugpy.wait_for_client();

#rules = load_definitions("./detector.json");
det=Detector("./detector.json");
rules=det.get_rules();
print(rules);
fields=rules['fields'];
print(fields);
print(fields[1]);