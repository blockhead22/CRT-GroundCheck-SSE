"""Force logout all users by clearing sessions table"""
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
}

print(f"Connecting to {config['user']}@{config['host']}/{config['database']}...")

try:
    conn = pymysql.connect(**config)
    cursor = conn.cursor()
    
    # Count existing sessions
    cursor.execute("SELECT COUNT(*) as count FROM sessions")
    result = cursor.fetchone()
    session_count = result[0]
    
    print(f"\nFound {session_count} active session(s)")
    
    if session_count > 0:
        # Delete all sessions
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        print(f"✓ Deleted {cursor.rowcount} session(s)")
        print("\n✅ All users have been logged out!")
    else:
        print("\n✓ No active sessions found")
    
    conn.close()
    
except pymysql.Error as e:
    print(f"✗ Error: {e}")
