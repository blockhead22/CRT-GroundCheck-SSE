"""
MySQL Database Setup Script for CRT
This script helps set up the MySQL database on nickblockdesigns.com
"""

import pymysql
import sys
from getpass import getpass


def test_connection(config):
    """Test MySQL connection with given config."""
    try:
        conn = pymysql.connect(**config)
        print("✓ Connection successful!")
        conn.close()
        return True
    except pymysql.Error as e:
        print(f"✗ Connection failed: {e}")
        return False


def setup_database(config):
    """Set up the CRT database schema."""
    try:
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        # Create tables
        print("\nCreating tables...")
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(64) NOT NULL,
                password_salt VARCHAR(32) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                INDEX idx_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✓ Users table created")
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token VARCHAR(64) PRIMARY KEY,
                user_id INT NOT NULL,
                created_at BIGINT NOT NULL,
                expires_at BIGINT NOT NULL,
                user_agent TEXT,
                ip_address VARCHAR(45),
                INDEX idx_user_id (user_id),
                INDEX idx_expires_at (expires_at),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✓ Sessions table created")
        
        # Chat threads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_chat_threads (
                id VARCHAR(255) PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(500) NOT NULL,
                messages LONGTEXT NOT NULL DEFAULT '[]',
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                INDEX idx_user_id (user_id),
                INDEX idx_updated_at (updated_at),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✓ Chat threads table created")
        
        conn.commit()
        conn.close()
        
        print("\n✓ Database setup complete!")
        return True
        
    except pymysql.Error as e:
        print(f"\n✗ Error setting up database: {e}")
        return False


def main():
    print("=" * 60)
    print("CRT MySQL Database Setup")
    print("=" * 60)
    
    print("\nDefault configuration:")
    print(f"  Host: nickblockdesigns.com")
    print(f"  User: crt_api")
    print(f"  Database: crt_users")
    print(f"  Port: 3306")
    
    use_defaults = input("\nUse default settings? (y/n): ").lower().strip() == 'y'
    
    if use_defaults:
        host = "nickblockdesigns.com"
        user = "crt_api"
        database = "crt_users"
        port = 3306
        password = getpass("Enter password: ")
    else:
        host = input("MySQL Host: ").strip() or "nickblockdesigns.com"
        user = input("MySQL User: ").strip() or "crt_api"
        database = input("MySQL Database: ").strip() or "crt_users"
        port = int(input("MySQL Port (3306): ").strip() or "3306")
        password = getpass("Password: ")
    
    config = {
        'host': host,
        'user': user,
        'password': password,
        'database': database,
        'port': port,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    
    print("\n" + "=" * 60)
    print("Testing connection...")
    print("=" * 60)
    
    if test_connection(config):
        print("\n" + "=" * 60)
        setup = input("Proceed with database setup? (y/n): ").lower().strip()
        if setup == 'y':
            setup_database(config)
        else:
            print("Setup cancelled.")
    else:
        print("\n" + "=" * 60)
        print("TROUBLESHOOTING TIPS:")
        print("=" * 60)
        print("\nIf you're getting 'Access denied' errors, you need to:")
        print("\n1. Log into your GoDaddy cPanel")
        print("2. Go to 'MySQL Databases'")
        print("3. Create a database named: crt_users")
        print("4. Create a MySQL user named: crt_api")
        print("5. Set a secure password")
        print("6. Add the user to the database with ALL PRIVILEGES")
        print("7. Under 'Remote MySQL', add your IP address or '%' for all IPs")
        print("\nAlternatively, contact GoDaddy support to enable remote MySQL access.")
        print("\nFor local testing, you can:")
        print("  1. Set USE_MYSQL=false in your .env file")
        print("  2. The system will use SQLite instead")


if __name__ == "__main__":
    main()
