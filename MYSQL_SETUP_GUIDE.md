# MySQL Setup Guide for GoDaddy Hosting

## Current Status
✓ Backend code is configured for MySQL  
✓ Password is correctly set in .env file  
✗ Database needs to be created in GoDaddy cPanel  

## Step-by-Step Setup in GoDaddy cPanel

### 1. Log into GoDaddy cPanel
- Go to https://www.godaddy.com/
- Navigate to your hosting account
- Click "cPanel Admin"

### 2. Create the MySQL Database
1. In cPanel, find "**Databases**" section
2. Click "**MySQL® Databases**"
3. Under "**Create New Database**":
   - Database Name: `crt_users`
   - Click "Create Database"
4. Note the full database name (GoDaddy may prefix it with your account name)
   - Example: `youraccountname_crt_users`

### 3. Create the MySQL User
1. Scroll down to "**MySQL Users**" section
2. Under "**Add New User**":
   - Username: `crt_api`
   - Password: `Bucks4010!!`
   - Click "Create User"
3. Note the full username (may be prefixed)
   - Example: `youraccountname_crt_api`

### 4. Link User to Database
1. Scroll to "**Add User To Database**" section
2. Select:
   - User: `crt_api` (or full name like `youraccountname_crt_api`)
   - Database: `crt_users` (or full name like `youraccountname_crt_users`)
3. Click "Add"
4. On the privileges page:
   - Check "**ALL PRIVILEGES**"
   - Click "Make Changes"

### 5. Enable Remote MySQL Access
1. In cPanel, find "**Databases**" section
2. Click "**Remote MySQL®**"
3. Under "**Add Access Host**":
   - Enter your current IP address OR
   - Enter `%` to allow all IPs (less secure but easier for testing)
4. Click "Add Host"

**To find your IP address:**
```bash
curl -s https://api.ipify.org && echo
```

### 6. Update .env File (if database/user names were prefixed)
If GoDaddy added a prefix to your database and username, update `.env`:

```env
MYSQL_HOST=nickblockdesigns.com
MYSQL_USER=youraccountname_crt_api
MYSQL_PASSWORD=Bucks4010!!
MYSQL_DATABASE=youraccountname_crt_users
MYSQL_PORT=3306
USE_MYSQL=true
```

### 7. Test the Connection
Run this command to test:
```bash
python test_mysql_connection.py
```

You should see:
```
✓ Connection successful!
```

### 8. Initialize Database Tables
Once connected, the backend will automatically create the necessary tables when it starts.

Or you can run the setup script manually:
```bash
python setup_mysql.py
```

### 9. Restart the Backend
Stop the current backend server (Ctrl+C) and restart it:
```bash
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123
```

You should see:
```
Using MySQL authentication backend
MySQL auth database initialized at nickblockdesigns.com/crt_users
```

## Troubleshooting

### Still Getting "Access Denied"?
1. Double-check the username and database name (they may have prefixes)
2. Verify the user is added to the database with ALL PRIVILEGES
3. Check Remote MySQL access is enabled for your IP
4. Some GoDaddy plans don't allow remote MySQL - contact support if needed

### Can't Enable Remote MySQL?
If GoDaddy doesn't allow remote MySQL access, you have two options:

**Option A: Use SQLite (Temporary)**
Update `.env`:
```env
USE_MYSQL=false
```
This will use local SQLite storage instead.

**Option B: SSH Tunnel (Advanced)**
If you have SSH access to your server:
```bash
ssh -L 3306:localhost:3306 user@nickblockdesigns.com
```

Then update `.env`:
```env
MYSQL_HOST=localhost
```

## Current Configuration
- Host: `nickblockdesigns.com`
- User: `crt_api`
- Password: `Bucks4010!!` (11 characters)
- Database: `crt_users`
- Port: `3306`

## Security Note
The `.env` file with your password is already in `.gitignore` and won't be committed to Git.
