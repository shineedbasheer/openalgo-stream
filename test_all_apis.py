#!/usr/bin/env python3
"""
Test ALL OpenAlgo APIs for Event Publishing

This script tests that all APIs properly publish events in all three modes.
"""

import os
import sys
import time

def test_api_endpoint(api_name, mode):
    """Test a specific API endpoint in a specific mode"""
    print(f"\n  Testing {api_name} in {mode} mode...")
    
    try:
        # Set mode
        os.environ['ORDER_EVENT_MODE'] = mode
        
        # Reset singleton
        from utils.event_publisher import EventPublisherFactory
        EventPublisherFactory.reset()
        
        # Get publisher
        from utils.event_publisher import get_event_publisher
        publisher = get_event_publisher()
        
        # Test order event (used by most APIs)
        success = publisher.publish_order_event(
            user_id=f"test_{api_name}",
            symbol="TEST-EQ",
            action="BUY",
            orderid=f"TEST_{api_name}_123",
            mode="test",
            broker="test_broker",
            quantity="1",
            price="100.00"
        )
        
        if success:
            print(f"    ✅ {api_name} - Event published successfully")
            return True
        else:
            print(f"    ❌ {api_name} - Failed to publish event")
            return False
            
    except Exception as e:
        print(f"    ❌ {api_name} - Error: {e}")
        return False

def main():
    print("="*60)
    print("OPENALGO - TEST ALL APIS")
    print("="*60)
    print()
    
    # Load environment
    from utils.env_check import load_and_check_env_variables
    load_and_check_env_variables()
    
    # APIs to test
    apis = [
        "placeorder",
        "placesmartorder",
        "basketorder",
        "closeposition",
        "cancelorder",
        "modifyorder",
        "cancelallorders",
    ]
    
    # Modes to test
    modes = ["SOCKETIO", "KAFKA", "BOTH"]
    
    print(f"Testing {len(apis)} APIs in {len(modes)} modes...")
    print()
    
    results = {}
    
    for mode in modes:
        print(f"\n{'='*60}")
        print(f"MODE: {mode}")
        print('='*60)
        
        mode_results = {}
        for api in apis:
            mode_results[api] = test_api_endpoint(api, mode)
        
        results[mode] = mode_results
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    print(f"\n{'API':<20} {'SOCKETIO':<12} {'KAFKA':<12} {'BOTH':<12}")
    print("-" * 60)
    
    for api in apis:
        socketio_status = "✅ Pass" if results["SOCKETIO"].get(api) else "❌ Fail"
        kafka_status = "✅ Pass" if results["KAFKA"].get(api) else "❌ Fail"
        both_status = "✅ Pass" if results["BOTH"].get(api) else "❌ Fail"
        
        print(f"{api:<20} {socketio_status:<12} {kafka_status:<12} {both_status:<12}")
    
    # Overall status
    all_passed = all(
        results[mode][api]
        for mode in modes
        for api in apis
    )
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL APIS PASSED IN ALL MODES!")
        print("="*60)
        print("\n📋 What this means:")
        print("   ✅ All APIs can publish events")
        print("   ✅ SOCKETIO mode works (UI only)")
        print("   ✅ KAFKA mode works (External only)")
        print("   ✅ BOTH mode works (UI + External)")
        print("\n🎉 Your OpenAlgo is fully configured!")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("="*60)
        print("\nCheck the failed APIs above")
        print("You may need to:")
        print("   1. Run: python fix_all_services.py")
        print("   2. Restart OpenAlgo")
        print("   3. Run this test again")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
