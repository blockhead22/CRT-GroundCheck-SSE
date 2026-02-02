"""List available MySQL databases"""
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
}

print(f"Connecting to {config['user']}@{config['host']}...")

try:
    # Connect without specifying a database
    conn = pymysql.connect(**config)
    print("✓ Connection successful!")
    
    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES")
    databases = cursor.fetchall()
    
    print(f"\n📊 Available databases ({len(databases)}):")
    for db in databases:
        db_name = db[0]
        # Highlight databases that might be ours
        if 'crt' in db_name.lower() or 'nick' in db_name.lower():
            print(f"  ⭐ {db_name}")
        else:
            print(f"     {db_name}")
    
    # Check if there's a prefixed version
    matching = [db[0] for db in databases if 'crt' in db[0].lower()]
    if matching:
        print(f"\n💡 Found CRT-related database(s): {matching}")
        print(f"   Update your .env file with:")
        print(f"   MYSQL_DATABASE={matching[0]}")
    
    conn.close()
    
except pymysql.Error as e:
    print(f"✗ Error: {e}")
