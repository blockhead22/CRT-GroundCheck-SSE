"""
View Moltbook Archive - Interactive Viewer
Shows all archived Moltbook.com interactions with clickable links
"""

from moltbook_archive import MoltbookArchiver
from datetime import datetime


def main():
    archiver = MoltbookArchiver()
    
    print("\n" + "=" * 80)
    print(" " * 25 + "🦞 MOLTBOOK ARCHIVE 🦞")
    print("=" * 80)
    
    stats = archiver.get_stats()
    
    print(f"\n📊 STATISTICS")
    print(f"  ✅ Posts Created:      {stats['total_posts']}")
    print(f"  💬 Comments Made:      {stats['total_comments']}")
    print(f"  ⬆️  Upvotes Given:      {stats['total_upvotes']}")
    print(f"  🔍 Searches Performed: {stats['total_searches']}")
    print(f"  📬 Feed Checks:        {stats['total_feed_checks']}")
    
    if stats['last_post_at']:
        print(f"\n  📅 Last Post: {stats['last_post_at']}")
    
    print("\n" + "-" * 80)
    
    # Show all posts
    posts = archiver.get_recent_posts(100)  # Get all
    if posts:
        print(f"\n📝 ALL POSTS ({len(posts)})")
        print("-" * 80)
        
        for post in posts:
            print(f"\n  #{post['id']} - m/{post['submolt']}")
            print(f"  📌 {post['title']}")
            
            if post['content']:
                content = post['content'][:100]
                if len(post['content']) > 100:
                    content += "..."
                print(f"  📄 {content}")
            
            if post['moltbook_url']:
                print(f"  🔗 {post['moltbook_url']}")
            else:
                print(f"  ❌ Post failed - check archive for details")
            
            print(f"  📅 {post['created_at']}")
            print()
    else:
        print("\n📝 NO POSTS YET")
        print("  Create your first post with:")
        print('  python moltbook_connector.py post "Title" "Content" general')
    
    print("-" * 80)
    
    # Show all comments
    comments = archiver.get_recent_comments(100)  # Get all
    if comments:
        print(f"\n💬 ALL COMMENTS ({len(comments)})")
        print("-" * 80)
        
        for comment in comments:
            print(f"\n  #{comment['id']}")
            
            if comment['post_title']:
                print(f"  📍 On post: {comment['post_title']}")
            else:
                print(f"  📍 On post ID: {comment['moltbook_post_id']}")
            
            content = comment['content'][:150]
            if len(comment['content']) > 150:
                content += "..."
            print(f"  💬 {content}")
            
            if comment['moltbook_url']:
                print(f"  🔗 {comment['moltbook_url']}")
            else:
                print(f"  ❌ Comment failed - check archive for details")
            
            print(f"  📅 {comment['created_at']}")
            print()
    else:
        print("\n💬 NO COMMENTS YET")
        print("  Comment on a post with:")
        print("  python moltbook_connector.py comment POST_ID 'Your comment'")
    
    print("-" * 80)
    
    # Show all links organized
    links = archiver.get_all_moltbook_links()
    all_links = links['posts'] + links['comments']
    
    if all_links:
        print(f"\n🔗 ALL MOLTBOOK LINKS ({len(all_links)})")
        print("-" * 80)
        
        for link in all_links[:20]:  # Show first 20
            if 'title' in link:  # Post
                print(f"\n  📌 {link['title']}")
            else:  # Comment
                print(f"\n  💬 Comment on: {link.get('post_title', 'Unknown')}")
            
            print(f"  🔗 {link['url']}")
            print(f"  📅 {link['created_at']}")
        
        if len(all_links) > 20:
            print(f"\n  ... and {len(all_links) - 20} more links")
    
    print("\n" + "=" * 80)
    
    # Export option
    print("\n💡 TIP: Export all links to markdown with:")
    print("   python moltbook_connector.py archive export")
    print("\n   Or programmatically:")
    print("   from moltbook_archive import MoltbookArchiver")
    print("   archiver = MoltbookArchiver()")
    print("   archiver.export_links_markdown('my_links.md')")
    print()


if __name__ == "__main__":
    main()
