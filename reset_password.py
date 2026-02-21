#!/usr/bin/env python3
"""
OpenAlgo Password Reset Script
================================
This script allows you to reset user passwords and view user information.

Usage:
    python reset_password.py

Requirements:
    - Must be run from the openalgo-stream directory
    - Requires .env file with DATABASE_URL and API_KEY_PEPPER
"""

import os
import sys
from sqlalchemy import text
from getpass import getpass

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from utils.env_check import load_and_check_env_variables
load_and_check_env_variables()

import pyotp
from argon2 import PasswordHasher
from database.user_db import User, db_session, PASSWORD_PEPPER

# Initialize Argon2 hasher
ph = PasswordHasher()


def list_users():
    """List all users in the database"""
    print("\n" + "=" * 60)
    print("CURRENT USERS IN DATABASE")
    print("=" * 60)
    
    users = User.query.all()
    
    if not users:
        print("\nNo users found in the database.")
        return False
    
    for idx, user in enumerate(users, 1):
        print(f"\n{idx}. Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Is Admin: {user.is_admin}")
        print(f"   TOTP Secret: {user.totp_secret}")
    
    print("\n" + "=" * 60)
    return True


def reset_password(username):
    """Reset password for a specific user"""
    user = User.query.filter_by(username=username).first()
    
    if not user:
        print(f"\n❌ Error: User '{username}' not found!")
        return False
    
    print(f"\n✓ Found user: {username} ({user.email})")
    
    # Get new password
    while True:
        new_password = getpass("\nEnter new password: ")
        if len(new_password) < 8:
            print("❌ Password must be at least 8 characters long!")
            continue
            
        confirm_password = getpass("Confirm new password: ")
        
        if new_password != confirm_password:
            print("❌ Passwords do not match! Please try again.")
            continue
        
        break
    
    # Update password
    try:
        user.set_password(new_password)
        db_session.commit()
        print(f"\n✅ Password successfully reset for user: {username}")
        return True
    except Exception as e:
        print(f"\n❌ Error resetting password: {e}")
        db_session.rollback()
        return False


def reset_totp_secret(username):
    """Generate new TOTP secret for a user"""
    user = User.query.filter_by(username=username).first()
    
    if not user:
        print(f"\n❌ Error: User '{username}' not found!")
        return False
    
    print(f"\n⚠️  WARNING: This will generate a new TOTP secret.")
    print("You will need to reconfigure your authenticator app!")
    
    confirm = input("\nAre you sure you want to continue? (yes/no): ").lower()
    
    if confirm != 'yes':
        print("Operation cancelled.")
        return False
    
    try:
        # Generate new TOTP secret
        new_secret = pyotp.random_base32()
        user.totp_secret = new_secret
        db_session.commit()
        
        print(f"\n✅ New TOTP secret generated for user: {username}")
        print(f"\nTOTP Secret: {new_secret}")
        print(f"\nSetup URI (for QR code):")
        print(f"{user.get_totp_uri()}")
        
        # Optionally generate QR code
        try:
            import qrcode
            import io
            
            generate_qr = input("\nGenerate QR code in terminal? (yes/no): ").lower()
            if generate_qr == 'yes':
                qr = qrcode.QRCode()
                qr.add_data(user.get_totp_uri())
                qr.print_ascii()
        except ImportError:
            print("\n💡 Tip: Install 'qrcode' package to generate QR codes:")
            print("   pip install qrcode[pil]")
        
        return True
    except Exception as e:
        print(f"\n❌ Error resetting TOTP secret: {e}")
        db_session.rollback()
        return False


def create_new_user():
    """Create a new user"""
    print("\n" + "=" * 60)
    print("CREATE NEW USER")
    print("=" * 60)
    
    username = input("\nEnter username: ").strip()
    email = input("Enter email: ").strip()
    
    # Check if user already exists
    if User.query.filter_by(username=username).first():
        print(f"\n❌ Error: Username '{username}' already exists!")
        return False
    
    if User.query.filter_by(email=email).first():
        print(f"\n❌ Error: Email '{email}' already exists!")
        return False
    
    # Get password
    while True:
        password = getpass("\nEnter password: ")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters long!")
            continue
            
        confirm_password = getpass("Confirm password: ")
        
        if password != confirm_password:
            print("❌ Passwords do not match! Please try again.")
            continue
        
        break
    
    # Ask if admin
    is_admin_input = input("\nMake this user an admin? (yes/no): ").lower()
    is_admin = is_admin_input == 'yes'
    
    try:
        # Generate TOTP secret
        totp_secret = pyotp.random_base32()
        
        # Create user
        user = User(
            username=username,
            email=email,
            totp_secret=totp_secret,
            is_admin=is_admin
        )
        user.set_password(password)
        
        db_session.add(user)
        db_session.commit()
        
        print(f"\n✅ User '{username}' created successfully!")
        print(f"\nTOTP Secret: {totp_secret}")
        print(f"Setup URI: {user.get_totp_uri()}")
        
        return True
    except Exception as e:
        print(f"\n❌ Error creating user: {e}")
        db_session.rollback()
        return False


def main_menu():
    """Display main menu and handle user input"""
    while True:
        print("\n" + "=" * 60)
        print("OPENALGO PASSWORD RESET UTILITY")
        print("=" * 60)
        print("\n1. List all users")
        print("2. Reset password")
        print("3. Reset TOTP secret (2FA)")
        print("4. Create new user")
        print("5. Exit")
        print("\n" + "=" * 60)
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            list_users()
            
        elif choice == '2':
            if not list_users():
                continue
            username = input("\nEnter username to reset password: ").strip()
            reset_password(username)
            
        elif choice == '3':
            if not list_users():
                continue
            username = input("\nEnter username to reset TOTP secret: ").strip()
            reset_totp_secret(username)
            
        elif choice == '4':
            create_new_user()
            
        elif choice == '5':
            print("\nExiting...")
            break
            
        else:
            print("\n❌ Invalid choice! Please enter a number between 1 and 5.")


if __name__ == "__main__":
    try:
        print("\n🔧 OpenAlgo Password Reset Utility")
        print("=" * 60)
        
        # Check if database is accessible
        try:
            db_session.execute(text("SELECT 1"))
            print("✓ Database connection successful")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            print("\nPlease make sure:")
            print("1. You're running this script from the openalgo-stream directory")
            print("2. The .env file exists and contains DATABASE_URL")
            print("3. The database file exists (if using SQLite)")
            sys.exit(1)
        
        main_menu()
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
