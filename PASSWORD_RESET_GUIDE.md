# OpenAlgo Username & Password Reset Guide

## Quick Summary

**OpenAlgo** uses secure Argon2 password hashing with TOTP-based 2FA. You have multiple options to reset credentials:

---

## Method 1: Web Interface (Easiest) ✅

### If you remember your email:

1. **Navigate to**: `http://localhost:5000/reset-password`
2. **Enter your email address**
3. **Choose reset method**:
   - **Option A - TOTP**: Use your authenticator app (Google Authenticator, Authy, etc.)
   - **Option B - Email**: Receive a reset link via email (requires SMTP configured)

---

## Method 2: Using the Reset Script (Recommended) 🔧

### Step 1: Run the script

```powershell
cd C:\workspace\openalgo-stream
python reset_password.py
```

### Step 2: Choose an option from the menu:

```
1. List all users        - View all registered users
2. Reset password        - Change password for existing user
3. Reset TOTP secret     - Generate new 2FA secret
4. Create new user       - Add a new user account
5. Exit                  - Exit the utility
```

### Example: Reset Password

```
Enter your choice: 2
Enter username to reset password: admin
Enter new password: ********
Confirm new password: ********
✅ Password successfully reset for user: admin
```

---

## Method 3: Direct Database Access (Advanced) 🗄️

### For SQLite Database:

```powershell
# Locate your database file
cd C:\workspace\openalgo-stream

# Open SQLite database
sqlite3 openalgo.db

# View users
SELECT id, username, email, is_admin FROM users;

# You cannot directly set passwords this way because they use Argon2 hashing
# Use Method 2 (reset script) instead!
```

---

## Method 4: Python Console (Advanced) 🐍

```powershell
cd C:\workspace\openalgo-stream
python
```

```python
# Import necessary modules
from database.user_db import User, db_session, add_user
from utils.env_check import load_and_check_env_variables

# Load environment
load_and_check_env_variables()

# List all users
users = User.query.all()
for user in users:
    print(f"Username: {user.username}, Email: {user.email}")

# Reset password for a user
user = User.query.filter_by(username='admin').first()
if user:
    user.set_password('YourNewPassword123')
    db_session.commit()
    print("Password reset successfully!")

# Create a new user
new_user = add_user(
    username='newuser',
    email='newuser@example.com',
    password='SecurePassword123',
    is_admin=False
)
if new_user:
    print(f"User created with TOTP secret: {new_user.totp_secret}")
```

---

## Important Information 📋

### Default Setup User

When you first install OpenAlgo, you create an admin user during setup. If you forgot this:

1. Check if any users exist:
   ```python
   python reset_password.py
   # Choose option 1 to list users
   ```

2. If no users exist, visit: `http://localhost:5000/setup`

### TOTP Secret (2FA)

- **Lost your TOTP secret?** Use the reset script (option 3) to generate a new one
- **View TOTP secret**: Use the reset script (option 1) to see existing secrets
- **QR Code**: The script can generate a QR code for easy setup in authenticator apps

### Password Requirements

- Minimum 8 characters
- Must include uppercase, lowercase, and numbers (recommended)
- Stored using Argon2 hashing (very secure)

### Email Reset (SMTP Configuration)

To use email-based password reset:

1. Go to **Profile > SMTP Settings** in the web interface
2. Configure your SMTP server details
3. Test the connection before using email reset

---

## Troubleshooting 🔍

### "Database connection failed"

**Solution**: 
```powershell
# Check if .env file exists
Get-Content C:\workspace\openalgo-stream\.env

# Look for DATABASE_URL line
# Should be something like:
DATABASE_URL=sqlite:///openalgo.db
# or
DATABASE_URL=postgresql://user:pass@localhost/openalgo
```

### "User not found"

**Solution**: List all users first:
```powershell
python reset_password.py
# Choose option 1
```

### "API_KEY_PEPPER not set"

**Solution**: Your `.env` file needs the pepper value:
```powershell
# Generate a new pepper
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env file:
API_KEY_PEPPER=<generated_value>
```

### "Cannot import module"

**Solution**: Install required dependencies:
```powershell
pip install -r requirements.txt
```

---

## Security Notes 🔒

1. **Never share** your TOTP secret or API_KEY_PEPPER
2. **Backup** your TOTP secret in a secure location
3. **Strong passwords** are enforced - use a password manager
4. **Argon2** hashing ensures passwords are securely stored
5. **2FA** adds an extra layer of security

---

## Quick Commands Cheat Sheet 📝

```powershell
# List users
python reset_password.py  # Option 1

# Reset password
python reset_password.py  # Option 2

# Create new user
python reset_password.py  # Option 4

# Check database location
Get-Content .env | Select-String "DATABASE_URL"

# View logs
Get-Content log\application.log -Tail 50
```

---

## Need More Help? 🆘

1. Check the official docs: https://docs.openalgo.in
2. GitHub Issues: https://github.com/marketcalls/openalgo
3. Discord Community: https://discord.com/invite/UPh7QPsNhP

---

**Created**: February 2025
**Version**: For OpenAlgo v2.x+
