#!/usr/bin/env python3
# JSON object reader that handles multi-line pretty-printed JSON

import sys
import json

def read_json_objects(stream):
    """
    Read complete JSON objects from a stream, handling multi-line JSON.
    Yields one complete JSON object at a time.
    """
    buffer = ""
    brace_count = 0
    in_string = False
    escape_next = False
    
    for line in stream:
        for char in line:
            buffer += char
            
            # Track string state to ignore braces in strings
            if char == '"' and not escape_next:
                in_string = not in_string
            
            escape_next = (char == '\\' and not escape_next)
            
            # Count braces when not in a string
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    # Complete JSON object when braces balance
                    if brace_count == 0 and buffer.strip():
                        try:
                            obj = json.loads(buffer)
                            yield obj
                            buffer = ""
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e}", file=sys.stderr)
                            buffer = ""

if __name__ == "__main__":
    # Test the reader
    for obj in read_json_objects(sys.stdin):
        print(f"Got object: {obj.get('type', 'unknown')}")
