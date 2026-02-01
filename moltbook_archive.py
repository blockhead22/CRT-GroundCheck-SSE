"""
Moltbook Interaction Archive System
Automatically logs all Moltbook.com interactions with links and metadata.

Archives:
- Posts created (with Moltbook URLs)
- Comments made (with context)
- Upvotes given
- Searches performed
- Feed checks
- Profile views

Storage: SQLite database at data/moltbook_archive.db
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager


class MoltbookArchiver:
    def __init__(self, db_path: str = "data/moltbook_archive.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize archive database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    moltbook_post_id TEXT,
                    submolt TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    url TEXT,
                    moltbook_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_json TEXT,
                    status TEXT DEFAULT 'success'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    moltbook_comment_id TEXT,
                    moltbook_post_id TEXT NOT NULL,
                    parent_comment_id TEXT,
                    content TEXT NOT NULL,
                    post_title TEXT,
                    post_submolt TEXT,
                    moltbook_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_json TEXT,
                    status TEXT DEFAULT 'success'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS upvotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    moltbook_post_id TEXT,
                    moltbook_comment_id TEXT,
                    target_type TEXT NOT NULL,
                    target_title TEXT,
                    author_name TEXT,
                    follow_suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_json TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    search_type TEXT DEFAULT 'all',
                    result_count INTEGER,
                    top_result_id TEXT,
                    top_result_similarity REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_json TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feed_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sort_type TEXT DEFAULT 'hot',
                    post_count INTEGER,
                    new_mentions BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_json TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_type TEXT NOT NULL,
                    target_id TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(moltbook_post_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at DESC)")
    
    def archive_post(self, submolt: str, title: str, content: str, 
                     response: Optional[Dict] = None, url: Optional[str] = None) -> int:
        """Archive a post creation."""
        with self._get_connection() as conn:
            post_id = None
            moltbook_url = None
            status = 'success'
            
            if response and response.get('success'):
                data = response.get('data', {})
                post_id = data.get('id')
                if post_id:
                    moltbook_url = f"https://www.moltbook.com/m/{submolt}/comments/{post_id}"
            else:
                status = 'failed'
            
            cursor = conn.execute("""
                INSERT INTO posts 
                (moltbook_post_id, submolt, title, content, url, moltbook_url, response_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(post_id) if post_id else None,
                submolt,
                title,
                content,
                url,
                moltbook_url,
                json.dumps(response) if response else None,
                status
            ))
            
            archive_id = cursor.lastrowid
            
            print(f"\n📦 ARCHIVED POST #{archive_id}")
            if moltbook_url:
                print(f"🔗 Moltbook URL: {moltbook_url}")
            
            return archive_id
    
    def archive_comment(self, post_id: str, content: str, parent_id: Optional[str] = None,
                       response: Optional[Dict] = None, post_context: Optional[Dict] = None) -> int:
        """Archive a comment creation."""
        with self._get_connection() as conn:
            comment_id = None
            moltbook_url = None
            status = 'success'
            post_title = None
            post_submolt = None
            
            if post_context:
                post_title = post_context.get('title')
                post_submolt = post_context.get('submolt')
            
            if response and response.get('success'):
                data = response.get('data', {})
                comment_id = data.get('id')
                if comment_id and post_submolt:
                    moltbook_url = f"https://www.moltbook.com/m/{post_submolt}/comments/{post_id}#{comment_id}"
            else:
                status = 'failed'
            
            cursor = conn.execute("""
                INSERT INTO comments 
                (moltbook_comment_id, moltbook_post_id, parent_comment_id, content, 
                 post_title, post_submolt, moltbook_url, response_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(comment_id) if comment_id else None,
                str(post_id),
                str(parent_id) if parent_id else None,
                content,
                post_title,
                post_submolt,
                moltbook_url,
                json.dumps(response) if response else None,
                status
            ))
            
            archive_id = cursor.lastrowid
            
            print(f"\n📦 ARCHIVED COMMENT #{archive_id}")
            if moltbook_url:
                print(f"🔗 Moltbook URL: {moltbook_url}")
            
            return archive_id
    
    def archive_upvote(self, target_id: str, target_type: str, response: Optional[Dict] = None) -> int:
        """Archive an upvote."""
        with self._get_connection() as conn:
            author_name = None
            follow_suggestion = None
            
            if response:
                author = response.get('author', {})
                author_name = author.get('name') if isinstance(author, dict) else None
                
                if not response.get('already_following'):
                    follow_suggestion = response.get('suggestion')
            
            post_id = target_id if target_type == 'post' else None
            comment_id = target_id if target_type == 'comment' else None
            
            cursor = conn.execute("""
                INSERT INTO upvotes 
                (moltbook_post_id, moltbook_comment_id, target_type, author_name, 
                 follow_suggestion, response_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                post_id,
                comment_id,
                target_type,
                author_name,
                follow_suggestion,
                json.dumps(response) if response else None
            ))
            
            archive_id = cursor.lastrowid
            
            print(f"\n📦 ARCHIVED UPVOTE #{archive_id}")
            if follow_suggestion:
                print(f"💡 {follow_suggestion}")
            
            return archive_id
    
    def archive_search(self, query: str, search_type: str, results: List[Dict]) -> int:
        """Archive a search query and results."""
        with self._get_connection() as conn:
            top_result_id = None
            top_similarity = None
            
            if results:
                top = results[0]
                top_result_id = str(top.get('id'))
                top_similarity = top.get('similarity')
            
            cursor = conn.execute("""
                INSERT INTO searches 
                (query, search_type, result_count, top_result_id, top_result_similarity, response_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                query,
                search_type,
                len(results),
                top_result_id,
                top_similarity,
                json.dumps(results[:10]) if results else None  # Store top 10
            ))
            
            archive_id = cursor.lastrowid
            
            print(f"\n📦 ARCHIVED SEARCH #{archive_id}")
            print(f"🔍 Query: '{query}' → {len(results)} results")
            
            return archive_id
    
    def archive_feed_check(self, sort_type: str, posts: List[Dict], has_mentions: bool = False) -> int:
        """Archive a feed check."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO feed_checks 
                (sort_type, post_count, new_mentions, response_json)
                VALUES (?, ?, ?, ?)
            """, (
                sort_type,
                len(posts),
                has_mentions,
                json.dumps(posts[:20]) if posts else None  # Store top 20
            ))
            
            archive_id = cursor.lastrowid
            
            print(f"\n📦 ARCHIVED FEED CHECK #{archive_id}")
            print(f"📬 {len(posts)} posts ({sort_type})")
            if has_mentions:
                print("🔔 New mentions detected!")
            
            return archive_id
    
    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """Get recent archived posts with links."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM posts 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_comments(self, limit: int = 10) -> List[Dict]:
        """Get recent archived comments with links."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM comments 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_moltbook_links(self) -> Dict[str, List[str]]:
        """Get all Moltbook URLs organized by type."""
        with self._get_connection() as conn:
            # Get post URLs
            cursor = conn.execute("""
                SELECT moltbook_url, title, created_at 
                FROM posts 
                WHERE moltbook_url IS NOT NULL 
                ORDER BY created_at DESC
            """)
            post_links = [
                {
                    'url': row['moltbook_url'],
                    'title': row['title'],
                    'created_at': row['created_at']
                }
                for row in cursor.fetchall()
            ]
            
            # Get comment URLs
            cursor = conn.execute("""
                SELECT moltbook_url, post_title, created_at 
                FROM comments 
                WHERE moltbook_url IS NOT NULL 
                ORDER BY created_at DESC
            """)
            comment_links = [
                {
                    'url': row['moltbook_url'],
                    'post_title': row['post_title'],
                    'created_at': row['created_at']
                }
                for row in cursor.fetchall()
            ]
            
            return {
                'posts': post_links,
                'comments': comment_links
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get archive statistics."""
        with self._get_connection() as conn:
            stats = {}
            
            # Post count
            cursor = conn.execute("SELECT COUNT(*) as count FROM posts WHERE status = 'success'")
            stats['total_posts'] = cursor.fetchone()['count']
            
            # Comment count
            cursor = conn.execute("SELECT COUNT(*) as count FROM comments WHERE status = 'success'")
            stats['total_comments'] = cursor.fetchone()['count']
            
            # Upvote count
            cursor = conn.execute("SELECT COUNT(*) as count FROM upvotes")
            stats['total_upvotes'] = cursor.fetchone()['count']
            
            # Search count
            cursor = conn.execute("SELECT COUNT(*) as count FROM searches")
            stats['total_searches'] = cursor.fetchone()['count']
            
            # Feed checks
            cursor = conn.execute("SELECT COUNT(*) as count FROM feed_checks")
            stats['total_feed_checks'] = cursor.fetchone()['count']
            
            # Most recent activity
            cursor = conn.execute("""
                SELECT created_at FROM posts 
                WHERE status = 'success' 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            stats['last_post_at'] = row['created_at'] if row else None
            
            return stats
    
    def export_links_markdown(self, output_path: str = "moltbook_links.md"):
        """Export all links to a markdown file."""
        links = self.get_all_moltbook_links()
        stats = self.get_stats()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Moltbook.com Archive\n\n")
            f.write(f"**Agent:** AetherCRT\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Statistics\n\n")
            f.write(f"- **Posts Created:** {stats['total_posts']}\n")
            f.write(f"- **Comments Made:** {stats['total_comments']}\n")
            f.write(f"- **Upvotes Given:** {stats['total_upvotes']}\n")
            f.write(f"- **Searches Performed:** {stats['total_searches']}\n")
            f.write(f"- **Feed Checks:** {stats['total_feed_checks']}\n\n")
            
            f.write("---\n\n")
            
            f.write("## Posts\n\n")
            if links['posts']:
                for post in links['posts']:
                    f.write(f"### [{post['title']}]({post['url']})\n")
                    f.write(f"*Posted: {post['created_at']}*\n\n")
            else:
                f.write("*No posts yet*\n\n")
            
            f.write("---\n\n")
            
            f.write("## Comments\n\n")
            if links['comments']:
                for comment in links['comments']:
                    title = comment['post_title'] or 'Unknown Post'
                    f.write(f"- [{title}]({comment['url']}) - {comment['created_at']}\n")
            else:
                f.write("*No comments yet*\n\n")
        
        print(f"\n📄 Exported links to: {output_path}")
        return output_path


def main():
    """Demo: View archive stats and export links."""
    archiver = MoltbookArchiver()
    
    print("\n📊 MOLTBOOK ARCHIVE STATISTICS")
    print("=" * 60)
    
    stats = archiver.get_stats()
    print(f"\n✅ Posts Created: {stats['total_posts']}")
    print(f"💬 Comments Made: {stats['total_comments']}")
    print(f"⬆️  Upvotes Given: {stats['total_upvotes']}")
    print(f"🔍 Searches: {stats['total_searches']}")
    print(f"📬 Feed Checks: {stats['total_feed_checks']}")
    
    if stats['last_post_at']:
        print(f"\n📅 Last Post: {stats['last_post_at']}")
    
    print("\n" + "=" * 60)
    
    # Show recent posts
    recent_posts = archiver.get_recent_posts(5)
    if recent_posts:
        print("\n📝 RECENT POSTS:")
        for post in recent_posts:
            print(f"\n  • {post['title']}")
            if post['moltbook_url']:
                print(f"    🔗 {post['moltbook_url']}")
            print(f"    📅 {post['created_at']}")
    
    # Export links
    print("\n")
    archiver.export_links_markdown()


if __name__ == "__main__":
    main()
