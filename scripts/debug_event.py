#!/usr/bin/env python3
# Debug script to see what events look like

import sys
sys.path.insert(0, 'src/pipeline')

from json_reader import read_json_objects
from event_parsers import parse_json_line
import json

print("Looking for block or network event...")

# Read events until we find a block or network one
for obj in read_json_objects(sys.stdin):
    obj_type = obj.get('type', 'unknown')
    
    # Skip until we find block or network
    if obj_type not in ['blockstats', 'net_interface']:
        print(f"Skipping {obj_type}...")
        continue
    
    print(f"\n=== FOUND {obj_type.upper()} EVENT ===")
    print("\n=== RAW OBJECT FROM JSON READER ===")
    print(json.dumps(obj, indent=2))
    
    print("\n=== AFTER CONVERTING TO STRING AND PARSING ===")
    line = json.dumps(obj)
    result = parse_json_line(line)
    
    if result:
        event_type, parsed_event = result
        print(f"Event type: {event_type}")
        print(f"Parsed event keys: {list(parsed_event.keys())}")
        print(f"\nFull event:")
        print(json.dumps(parsed_event, indent=2))
        
        # Check specific fields
        if 'device_name' in parsed_event:
            print(f"\n✓ device_name present: {parsed_event['device_name']}")
        else:
            print(f"\n✗ device_name MISSING")
            if 'device' in obj:
                print(f"  Original had 'device': {obj['device']}")
                
        if 'interface_name' in parsed_event:
            print(f"✓ interface_name present: {parsed_event['interface_name']}")
        else:
            print(f"✗ interface_name MISSING")
            if 'interface' in obj:
                print(f"  Original had 'interface': {obj['interface']}")
    
    break  # Found one, exit
