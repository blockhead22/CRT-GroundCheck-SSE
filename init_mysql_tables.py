"""Initialize MySQL database tables for CRT"""
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
    
    print("✓ Connected!\n")
    print("Creating tables...")
    
    # Users table
    print("  Creating 'users' table...")
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
    print("  ✓ Users table created")
    
    # Sessions table
    print("  Creating 'sessions' table...")
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
    print("  ✓ Sessions table created")
    
    # Chat threads table
    print("  Creating 'user_chat_threads' table...")
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
    print("  ✓ Chat threads table created")
    
    conn.commit()
    
    # Verify tables
    print("\nVerifying tables...")
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"\n📊 Tables in database ({len(tables)}):")
    for table in tables:
        print(f"  ✓ {table[0]}")
    
    conn.close()
    
    print("\n✅ Database initialization complete!")
    print("The backend can now use MySQL for user authentication and chat history.")
    
except pymysql.Error as e:
    print(f"✗ Error: {e}")
