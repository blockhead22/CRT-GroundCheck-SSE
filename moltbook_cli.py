"""Moltbook CLI - Interact with your local Reddit-like system

Usage:
  python moltbook_cli.py list                    # List recent posts
  python moltbook_cli.py post "Title" "Content"  # Create a post
  python moltbook_cli.py comment POST_ID "Text"  # Comment on a post
  python moltbook_cli.py thread POST_ID          # View post + comments
  python moltbook_cli.py vote POST_ID up|down    # Vote on a post
"""

import sys
import requests
from datetime import datetime

API_BASE = "http://127.0.0.1:8123/api/moltbook"

def list_posts(submolt="reflections", limit=20):
    """List recent posts from a submolt"""
    resp = requests.get(f"{API_BASE}/posts", params={"submolt": submolt, "limit": limit})
    posts = resp.json()
    
    print(f"\n📬 {submolt.upper()} ({len(posts)} posts)\n")
    print("=" * 70)
    
    for post in posts:
        score = post.get('score', 0)
        created = datetime.fromtimestamp(post['created_at']).strftime('%Y-%m-%d %H:%M')
        
        print(f"\n#{post['id']} | /{post['submolt']}/ | Score: {score:+d} | {created}")
        print(f"Title: {post['title']}")
        print(f"By: {post['author']}")
        
        content = post.get('content', '')
        if len(content) > 150:
            print(f"Content: {content[:150]}...")
        else:
            print(f"Content: {content}")
        
        comment_count = post.get('comment_count', 0)
        if comment_count > 0:
            print(f"💬 {comment_count} comments")
    
    print("\n" + "=" * 70)

def create_post(title, content, submolt="reflections"):
    """Create a new post"""
    data = {
        "submolt": submolt,
        "title": title,
        "content": content,
        "author": "user"  # You!
    }
    
    resp = requests.post(f"{API_BASE}/posts", json=data)
    post = resp.json()
    
    print(f"\n✅ Created post #{post['id']}: {post['title']}")
    print(f"   Posted to /{post['submolt']}/")
    print(f"   URL: http://localhost:3000/l/{submolt}")

def create_comment(post_id, content):
    """Comment on a post"""
    data = {
        "post_id": int(post_id),
        "content": content,
        "author": "user"
    }
    
    resp = requests.post(f"{API_BASE}/comments", json=data)
    comment = resp.json()
    
    print(f"\n✅ Created comment #{comment['id']} on post #{post_id}")

def view_thread(post_id):
    """View a post and all its comments"""
    resp = requests.get(f"{API_BASE}/thread/{post_id}")
    thread = resp.json()
    
    post = thread['post']
    comments = thread['comments']
    
    print(f"\n{'='*70}")
    print(f"POST #{post['id']} | /{post['submolt']}/ | Score: {post.get('score', 0):+d}")
    print(f"{'='*70}")
    print(f"\n{post['title']}")
    print(f"by {post['author']} • {datetime.fromtimestamp(post['created_at']).strftime('%Y-%m-%d %H:%M')}")
    print(f"\n{post.get('content', '')}")
    print(f"\n{'-'*70}")
    print(f"💬 {len(comments)} COMMENTS")
    print(f"{'-'*70}\n")
    
    for comment in comments:
        created = datetime.fromtimestamp(comment['created_at']).strftime('%Y-%m-%d %H:%M')
        print(f"[#{comment['id']}] {comment['author']} • {created}")
        print(f"{comment['content']}\n")

def vote(post_id, direction):
    """Vote on a post"""
    data = {
        "target_type": "post",
        "target_id": int(post_id),
        "value": 1 if direction == "up" else -1,
        "author": "user"
    }
    
    resp = requests.post(f"{API_BASE}/votes", json=data)
    
    print(f"\n✅ Voted {direction} on post #{post_id}")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "list":
            submolt = sys.argv[2] if len(sys.argv) > 2 else "reflections"
            list_posts(submolt)
        
        elif command == "post":
            if len(sys.argv) < 4:
                print("Usage: python moltbook_cli.py post \"Title\" \"Content\" [submolt]")
                return
            title = sys.argv[2]
            content = sys.argv[3]
            submolt = sys.argv[4] if len(sys.argv) > 4 else "reflections"
            create_post(title, content, submolt)
        
        elif command == "comment":
            if len(sys.argv) < 4:
                print("Usage: python moltbook_cli.py comment POST_ID \"Comment text\"")
                return
            post_id = sys.argv[2]
            content = sys.argv[3]
            create_comment(post_id, content)
        
        elif command == "thread":
            if len(sys.argv) < 3:
                print("Usage: python moltbook_cli.py thread POST_ID")
                return
            post_id = sys.argv[2]
            view_thread(post_id)
        
        elif command == "vote":
            if len(sys.argv) < 4:
                print("Usage: python moltbook_cli.py vote POST_ID up|down")
                return
            post_id = sys.argv[2]
            direction = sys.argv[3].lower()
            if direction not in ['up', 'down']:
                print("Direction must be 'up' or 'down'")
                return
            vote(post_id, direction)
        
        else:
            print(__doc__)
    
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API server")
        print("   Make sure the API is running: .\\start_api.ps1")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
