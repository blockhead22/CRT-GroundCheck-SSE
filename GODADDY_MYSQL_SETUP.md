# GoDaddy MySQL Setup Guide for CRT

## What You Need to Do

To store user data on your GoDaddy MySQL database at nickblockdesigns.com, follow these steps:

### Step 1: Log into GoDaddy cPanel

1. Go to [GoDaddy](https://www.godaddy.com/)
2. Sign in to your account
3. Go to **My Products**
4. Click **cPanel Admin** next to your hosting account

### Step 2: Create the MySQL Database

1. In cPanel, scroll to the **Databases** section
2. Click **MySQL Databases**
3. Under "Create New Database":
   - Database Name: **crt_users**
   - Click **Create Database**

### Step 3: Create MySQL User

1. Scroll down to "Add New User"
   - Username: **crt_api**
   - Password: **Bucks4010!!** (or generate a strong one)
   - Click **Create User**

### Step 4: Add User to Database

1. Scroll to "Add User to Database"
   - Select User: **crt_api**
   - Select Database: **crt_users**
   - Click **Add**
2. On the privileges page:
   - Check **ALL PRIVILEGES**
   - Click **Make Changes**

### Step 5: Enable Remote MySQL Access

1. In cPanel, find **Remote MySQL** (in the Databases section)
2. Under "Add Access Host":
   - Enter your IP address: **72.135.252.185**
   - Or enter **%** to allow all IPs (less secure but easier for testing)
   - Click **Add Host**

**Important:** Your current IP address is **72.135.252.185** based on the connection attempts. If you're on a dynamic IP, you may need to add % or update this when your IP changes.

### Step 6: Note Your Database Credentials

After setup, your full credentials will be:
- **Host:** nickblockdesigns.com
- **Database:** crt_users (or might be prefixed like: youruser_crt_users)
- **Username:** crt_api (or might be prefixed like: youruser_crt_api)
- **Password:** Bucks4010!!
- **Port:** 3306

**Note:** GoDaddy often prefixes database and user names with your cPanel username. Check the actual names after creation.

### Step 7: Update Your .env File

Once you have the exact database name and username from GoDaddy, update `/Users/nickblock/Documents/AI_round2/.env`:

```env
MYSQL_HOST=nickblockdesigns.com
MYSQL_USER=yourprefix_crt_api  # Use the actual username from GoDaddy
MYSQL_PASSWORD=Bucks4010!!
MYSQL_DATABASE=yourprefix_crt_users  # Use the actual database name
MYSQL_PORT=3306
USE_MYSQL=true
```

### Step 8: Run the Setup Script

After configuring GoDaddy and updating .env, run:

```bash
cd /Users/nickblock/Documents/AI_round2
/Users/nickblock/Documents/AI_round2/.venv/bin/python setup_mysql.py
```

This will:
- Test the MySQL connection
- Create the required tables (users, sessions, user_chat_threads)

### Step 9: Restart the Backend

The backend will automatically reload when you change the .env file.

---

## Current Status

- ✅ Python MySQL libraries installed (pymysql, cryptography)
- ✅ MySQL auth module created (`auth_mysql.py`)
- ✅ Backend configured to support MySQL
- ⏳ **Waiting:** GoDaddy database setup and remote access configuration
- 🔄 **Currently using:** SQLite (local storage) until MySQL is ready

---

## Testing Locally with SQLite

For now, the system is using SQLite (local file storage). To switch back to MySQL after GoDaddy setup:

1. Complete steps 1-5 above
2. Update `.env` with the correct database/username (may have prefix)
3. Set `USE_MYSQL=true` in `.env`
4. The backend will auto-reload

---

## Troubleshooting

### "Access Denied" Error
- Make sure you added your IP (72.135.252.185) or % to Remote MySQL
- Verify the username/password are correct
- Check that the username/database don't have a prefix

### Can't Find Remote MySQL in cPanel
- Some GoDaddy plans don't allow remote MySQL
- Contact GoDaddy support to enable it
- Or use GoDaddy's phpMyAdmin from within cPanel

### Different Port or Host
- Some GoDaddy servers use different hostnames
- Check your hosting details for the MySQL hostname
- Standard port is 3306

---

## Security Notes

⚠️ **Important:**
- The `.env` file contains your password and is in `.gitignore` (won't be committed to git)
- Using `%` for remote access allows any IP - only use for testing
- Consider using a firewall or VPN for production
- Change passwords regularly
