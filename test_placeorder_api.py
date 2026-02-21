"""
Test PlaceOrder API Endpoint
This script tests if placeOrder API is working and publishing events
"""

import requests
import json

# Configuration
API_URL = "http://127.0.0.1:5000"
API_KEY = "YOUR_API_KEY_HERE"  # Replace with your actual API key

# Test order data
order_data = {
    "apikey": API_KEY,
    "strategy": "Test Strategy",
    "symbol": "SBIN-EQ",
    "action": "BUY",
    "exchange": "NSE",
    "price_type": "MARKET",
    "product_type": "MIS",
    "quantity": "1",
    "price": "0",
    "trigger_price": "0",
    "disclosed_quantity": "0"
}

print("=" * 80)
print("PlaceOrder API Test")
print("=" * 80)
print()

print("Test Order Data:")
print(json.dumps(order_data, indent=2))
print()

print("Sending PlaceOrder request...")
print("-" * 80)

try:
    response = requests.post(
        f"{API_URL}/api/v1/placeorder",
        json=order_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        print()
        print("✓ Order placed successfully!")
        print()
        print("Check your logs for:")
        print("  1. 'Publishing order event for order_id=...'")
        print("  2. 'Event publish result: True'")
        print()
        print("If you don't see these logs, the event is not being published.")
    else:
        print()
        print("✗ Order placement failed")
        
except requests.exceptions.ConnectionError:
    print("✗ Failed to connect to the API")
    print("  Make sure the Flask app is running at http://127.0.0.1:5000")
except Exception as e:
    print(f"✗ Error: {e}")

print()
print("=" * 80)
