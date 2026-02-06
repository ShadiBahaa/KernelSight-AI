#!/usr/bin/env python3
"""
Quick API Test Script

Run this to verify the API server is working correctly.
"""

import requests
import json
from time import sleep

API_BASE = "http://localhost:8000"

def test_api():
    """Test all API endpoints"""
    
    print("🧪 Testing KernelSight API Server\n")
    
    tests = []
    
    # Test 1: Health Check
    print("1️⃣  Health Check...")
    try:
        r = requests.get(f"{API_BASE}/api/health", timeout=5)
        r.raise_for_status()
        data = r.json()
        status = "✅" if data['status'] == 'healthy' else "⚠️"
        print(f"   {status} Status: {data['status']}, Signals: {data.get('signal_count', 0)}")
        tests.append(True)
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        tests.append(False)
    
    sleep(0.5)
    
    # Test 2: Signals
    print("\n2️⃣  Query Signals...")
    try:
        r = requests.get(f"{API_BASE}/api/signals?limit=5", timeout=5)
        r.raise_for_status()
        data = r.json()
        print(f"   ✅ Found {data['signal_count']} signals")
        tests.append(True)
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        tests.append(False)
    
    sleep(0.5)
    
    # Test 3: Stats
    print("\n3️⃣  System Stats...")
    try:
        r = requests.get(f"{API_BASE}/api/stats", timeout=5)
        r.raise_for_status()
        data = r.json()
        print(f"   ✅ Total signals: {data['total_signals']:,}")
        print(f"   ✅ Recent: {data['recent_signals']}")
        tests.append(True)
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        tests.append(False)
    
    sleep(0.5)
    
    # Test 4: Agent Status
    print("\n4️⃣  Agent Status...")
    try:
        r = requests.get(f"{API_BASE}/api/agent/status", timeout=5)
        r.raise_for_status()
        data = r.json()
        print(f"   ✅ Agent: {data['status']}")
        if data.get('activity'):
            print(f"   ✅ Recent activity: {len(data['activity'])} events")
        tests.append(True)
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        tests.append(False)
    
    sleep(0.5)
    
    # Test 5: Diagnostics
    print("\n5️⃣  Diagnostics...")
    try:
        r = requests.get(f"{API_BASE}/api/diagnostics", timeout=5)
        r.raise_for_status()
        data = r.json()
        overall = data['overall_status']
        icon = "✅" if overall == "healthy" else ("⚠️" if overall == "warning" else "❌")
        print(f"   {icon} Overall: {overall}")
        print(f"   ✅ Components checked: {len(data['checks'])}")
        tests.append(True)
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        tests.append(False)
    
    # Summary
    print("\n" + "="*50)
    passed = sum(tests)
    total = len(tests)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! API is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check if the system is running.")
        return 1


if __name__ == "__main__":
    print("Starting API tests...")
    print(f"Target: {API_BASE}\n")
    print("Make sure the API server is running:")
    print("  python3 api_server.py\n")
    
    try:
        exit_code = test_api()
        exit(exit_code)
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection refused. Is the API server running?")
        print("   Start it with: python3 api_server.py")
        exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted")
        exit(1)
