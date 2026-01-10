#!/usr/bin/env python3
"""Quick test of the evidence API"""

if __name__ == "__main__":
    import requests
    import json

    print("Testing Python Evidence API...")

    # Test health endpoint first
    try:
        resp = requests.get('http://127.0.0.1:5000/api/health', timeout=5)
        print(f"✅ Health check: {resp.status_code}")
        print(f"   Response: {resp.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        raise SystemExit(1)

    # Test search endpoint
    print("\nTesting search endpoint...")
    try:
        payload = {"query": "sleep", "k": 3}
        resp = requests.post(
            'http://127.0.0.1:5000/api/search',
            json=payload,
            timeout=30
        )
        print(f"✅ Search response: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"   Valid: {data.get('valid')}")
            print(f"   Query: {data.get('query')}")
            packet = data.get('packet', {})
            results = packet.get('query_results', [])
            print(f"   Results: {len(results)} clusters")
            if results:
                print(f"   First cluster ID: {results[0].get('cluster_id')}")
        else:
            print(f"   Error: {resp.text}")

    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
