#!/usr/bin/env python3
"""
OpenAlgo - Add BOTH Mode for Event Publishing

This script adds support for ORDER_EVENT_MODE='BOTH' which publishes events
to BOTH Socket.IO (for UI) and Kafka (for external systems) simultaneously.

Usage:
    python add_both_mode.py
"""

import os
import re
from pathlib import Path
from datetime import datetime

def backup_file(filepath):
    """Create a timestamped backup of the file before modifying"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Backed up: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to backup {filepath}: {e}")
        return False

def add_both_mode_to_event_publisher():
    """Add BOTH mode support to event_publisher.py"""
    
    filepath = Path("utils/event_publisher.py")
    
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return False
    
    print(f"\n📝 Processing: {filepath}")
    
    # Create backup
    if not backup_file(filepath):
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if BOTH mode already exists
        if "class BothEventPublisher" in content:
            print("  ℹ️  BOTH mode already exists in event_publisher.py")
            return True
        
        # Find the position to insert the new class (after KafkaEventPublisher)
        insertion_point = content.find("class EventPublisherFactory:")
        
        if insertion_point == -1:
            print("❌ Could not find EventPublisherFactory class")
            return False
        
        # Define the new BothEventPublisher class
        both_publisher_class = '''

class BothEventPublisher(EventPublisher):
    """
    Hybrid implementation - publishes to BOTH Socket.IO and Kafka
    
    This is useful when you want:
    - Real-time UI updates via Socket.IO (low latency for users)
    - External system integration via Kafka (event persistence and replay)
    """

    def __init__(self, socketio_instance, bootstrap_servers: str, topic: str):
        """
        Initialize Both event publisher
        
        Args:
            socketio_instance: Flask-SocketIO instance
            bootstrap_servers: Comma-separated Kafka broker addresses
            topic: Kafka topic name for publishing events
        """
        # Initialize both publishers
        self.socketio_publisher = SocketIOEventPublisher(socketio_instance)
        self.kafka_publisher = KafkaEventPublisher(bootstrap_servers, topic)
        logger.info(
            "BothEventPublisher initialized - publishing to Socket.IO AND Kafka\\n"
            f"  Kafka topic: {topic}\\n"
            f"  Kafka servers: {bootstrap_servers}"
        )

    def publish_order_event(
        self,
        user_id: str,
        symbol: str,
        action: str,
        orderid: str,
        mode: str,
        **kwargs
    ) -> bool:
        """Publish order event to BOTH Socket.IO and Kafka"""
        socketio_success = self.socketio_publisher.publish_order_event(
            user_id, symbol, action, orderid, mode, **kwargs
        )
        kafka_success = self.kafka_publisher.publish_order_event(
            user_id, symbol, action, orderid, mode, **kwargs
        )
        return socketio_success and kafka_success

    def publish_analyzer_update(
        self,
        user_id: str,
        request: Dict[str, Any],
        response: Dict[str, Any]
    ) -> bool:
        """Publish analyzer update to BOTH Socket.IO and Kafka"""
        socketio_success = self.socketio_publisher.publish_analyzer_update(
            user_id, request, response
        )
        kafka_success = self.kafka_publisher.publish_analyzer_update(
            user_id, request, response
        )
        return socketio_success and kafka_success

    def publish_order_notification(
        self,
        user_id: str,
        symbol: str,
        status: str,
        message: str,
        **kwargs
    ) -> bool:
        """Publish order notification to BOTH Socket.IO and Kafka"""
        socketio_success = self.socketio_publisher.publish_order_notification(
            user_id, symbol, status, message, **kwargs
        )
        kafka_success = self.kafka_publisher.publish_order_notification(
            user_id, symbol, status, message, **kwargs
        )
        return socketio_success and kafka_success

    def publish_master_contract_download(
        self,
        broker: str,
        status: str,
        message: str,
        **kwargs
    ) -> bool:
        """Publish master contract download event to BOTH Socket.IO and Kafka"""
        socketio_success = self.socketio_publisher.publish_master_contract_download(
            broker, status, message, **kwargs
        )
        kafka_success = self.kafka_publisher.publish_master_contract_download(
            broker, status, message, **kwargs
        )
        return socketio_success and kafka_success

    def publish_password_change(
        self,
        user_id: str,
        status: str,
        message: str,
        **kwargs
    ) -> bool:
        """Publish password change event to BOTH Socket.IO and Kafka"""
        socketio_success = self.socketio_publisher.publish_password_change(
            user_id, status, message, **kwargs
        )
        kafka_success = self.kafka_publisher.publish_password_change(
            user_id, status, message, **kwargs
        )
        return socketio_success and kafka_success

    def close(self) -> None:
        """Close both Socket.IO and Kafka publishers"""
        try:
            self.socketio_publisher.close()
            self.kafka_publisher.close()
            logger.info("Both publishers closed successfully")
        except Exception as e:
            logger.error(f"Error closing both publishers: {e}")


'''
        
        # Insert the new class before EventPublisherFactory
        content = content[:insertion_point] + both_publisher_class + content[insertion_point:]
        
        # Now update the EventPublisherFactory.create_publisher method to support BOTH mode
        factory_method_pattern = r'(class EventPublisherFactory:.*?@classmethod\s+def create_publisher\(cls\) -> EventPublisher:.*?)(mode = os\.getenv\(\'ORDER_EVENT_MODE\', \'SOCKETIO\'\)\.upper\(\)\s+if mode == \'KAFKA\':)'
        
        factory_replacement = r'''\1mode = os.getenv('ORDER_EVENT_MODE', 'SOCKETIO').upper()
        
        if mode == 'BOTH':
            # Validate configuration for both Socket.IO and Kafka
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
            topic = os.getenv('KAFKA_ORDER_EVENTS_TOPIC')
            
            if not bootstrap_servers:
                raise ValueError(
                    "BOTH mode requires KAFKA_BOOTSTRAP_SERVERS environment variable"
                )
            
            if not topic:
                raise ValueError(
                    "BOTH mode requires KAFKA_ORDER_EVENTS_TOPIC environment variable"
                )
            
            from extensions import socketio
            cls._instance = BothEventPublisher(socketio, bootstrap_servers, topic)
            logger.info("✓ Using BOTH Socket.IO and Kafka for order events")
            
        elif mode == 'KAFKA':'''
        
        content = re.sub(factory_method_pattern, factory_replacement, content, flags=re.DOTALL)
        
        # Update the error message for invalid modes
        content = re.sub(
            r"raise ValueError\(\s*f\"Invalid ORDER_EVENT_MODE: '\{mode\}'\. Must be 'SOCKETIO' or 'KAFKA'\"\s*\)",
            "raise ValueError(\n                f\"Invalid ORDER_EVENT_MODE: '{mode}'. Must be 'SOCKETIO', 'KAFKA', or 'BOTH'\"\n            )",
            content
        )
        
        # Write the modified content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Successfully added BOTH mode to {filepath}")
        return True
        
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_env_file():
    """Update .sample.env with BOTH mode documentation"""
    
    filepath = Path(".sample.env")
    
    if not filepath.exists():
        print(f"⚠️  .sample.env not found, skipping update")
        return True
    
    print(f"\n📝 Processing: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if BOTH mode documentation already exists
        if "BOTH (Socket.IO + Kafka)" in content:
            print("  ℹ️  BOTH mode already documented in .sample.env")
            return True
        
        # Update the ORDER_EVENT_MODE comment
        old_comment = "# Options: SOCKETIO (default), KAFKA"
        new_comment = "# Options: SOCKETIO (default), KAFKA, BOTH (Socket.IO + Kafka)"
        
        if old_comment in content:
            content = content.replace(old_comment, new_comment)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Updated {filepath} with BOTH mode documentation")
        else:
            print(f"  ℹ️  Could not find ORDER_EVENT_MODE comment to update")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False

def verify_config():
    """Verify current configuration"""
    print("\n" + "="*60)
    print("CONFIGURATION VERIFICATION")
    print("="*60)
    
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        return False
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    # Check ORDER_EVENT_MODE
    pattern = r"ORDER_EVENT_MODE\s*=\s*['\"]?([^'\"\\n]+)['\"]?"
    match = re.search(pattern, env_content)
    
    if match:
        value = match.group(1)
        print(f"Current ORDER_EVENT_MODE = {value}")
        
        if value == 'BOTH':
            print("✓ Already configured for BOTH mode")
        else:
            print(f"ℹ️  To enable BOTH mode, set ORDER_EVENT_MODE='BOTH' in .env")
    else:
        print("⚠️  ORDER_EVENT_MODE not found in .env")
    
    # Check Kafka config
    kafka_vars = ['KAFKA_BOOTSTRAP_SERVERS', 'KAFKA_ORDER_EVENTS_TOPIC']
    kafka_ok = True
    
    for var in kafka_vars:
        if var not in env_content or f"{var}=''" in env_content:
            print(f"⚠️  {var} not configured (required for BOTH mode)")
            kafka_ok = False
    
    if kafka_ok:
        print("✓ Kafka configuration present")
    
    print()
    return True

def main():
    print("="*60)
    print("OPENALGO - ADD BOTH MODE SUPPORT")
    print("="*60)
    print()
    print("This script adds support for ORDER_EVENT_MODE='BOTH'")
    print("Events will be published to Socket.IO AND Kafka simultaneously")
    print()
    
    # Verify we're in the correct directory
    if not os.path.exists('utils'):
        print("❌ Error: utils/ directory not found!")
        print("   Please run this script from the openalgo-stream directory")
        return
    
    # Add BOTH mode to event_publisher.py
    print("="*60)
    print("STEP 1: UPDATING EVENT PUBLISHER")
    print("="*60)
    
    if not add_both_mode_to_event_publisher():
        print("\n❌ Failed to update event_publisher.py")
        return
    
    # Update .sample.env documentation
    print("\n" + "="*60)
    print("STEP 2: UPDATING DOCUMENTATION")
    print("="*60)
    
    update_env_file()
    
    # Verify configuration
    verify_config()
    
    # Show success message
    print("="*60)
    print("✅ SUCCESS! BOTH MODE ADDED")
    print("="*60)
    print("\n📋 To use BOTH mode:")
    print("   1. Edit your .env file:")
    print("      ORDER_EVENT_MODE='BOTH'")
    print()
    print("   2. Restart OpenAlgo:")
    print("      python app.py")
    print()
    print("   3. Place a test order")
    print()
    print("   4. Verify events in BOTH places:")
    print()
    print("      A) UI: Check browser console for Socket.IO events")
    print("      B) Kafka: Run consumer:")
    print("         docker exec -it kafka-kafka-1 kafka-console-consumer \\")
    print("           --bootstrap-server localhost:9092 \\")
    print("           --topic from_openalgo_order_events \\")
    print("           --from-beginning")
    print()
    print("✨ Benefits of BOTH mode:")
    print("   • Real-time UI updates (Socket.IO)")
    print("   • External system integration (Kafka)")
    print("   • Event persistence and replay (Kafka)")
    print("   • Best of both worlds!")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
