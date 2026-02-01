"""
Moltbook.com Integration for CRT System
Connects your AI agent to the real Moltbook social network at https://www.moltbook.com

Usage:
    python moltbook_connector.py register                    # Register your agent
    python moltbook_connector.py status                      # Check claim status
    python moltbook_connector.py post "Title" "Content"       # Create a post
    python moltbook_connector.py feed                        # View your personalized feed
    python moltbook_connector.py comment POST_ID "Content"   # Comment on a post
    python moltbook_connector.py search "query"              # Semantic search
    python moltbook_connector.py profile [agent_name]        # View profile
    python moltbook_connector.py archive [export]            # View/export archive
    
Identity Tokens (for third-party app auth):
    python moltbook_connector.py identity                    # Generate identity token
    python moltbook_connector.py auth <app_url>              # Authenticate with app
"""

import requests
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Import archival system
try:
    from moltbook_archive import MoltbookArchiver
    ARCHIVING_ENABLED = True
except ImportError:
    ARCHIVING_ENABLED = False
    print("⚠️  Archiving disabled - moltbook_archive.py not found")

# Import privacy filter
try:
    from privacy_filter import PrivacyFilter
    PRIVACY_FILTER_ENABLED = True
except ImportError:
    PRIVACY_FILTER_ENABLED = False
    print("⚠️  Privacy filter disabled - privacy_filter.py not found")

# IMPORTANT: Always use www.moltbook.com to prevent auth header stripping
API_BASE = "https://www.moltbook.com/api/v1"

CREDENTIALS_PATH = Path.home() / ".config" / "moltbook" / "credentials.json"


class MoltbookClient:
    def __init__(self, api_key: Optional[str] = None, enable_archiving: bool = True):
        """Initialize Moltbook client. Auto-loads API key from config if available."""
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._load_credentials()
        
        # Initialize archiver
        self.archiver = None
        if enable_archiving and ARCHIVING_ENABLED:
            self.archiver = MoltbookArchiver()
            print("📦 Archiving enabled")
        
        # Initialize privacy filter
        self.privacy_filter = None
        if PRIVACY_FILTER_ENABLED:
            self.privacy_filter = PrivacyFilter()
            print("🔒 Privacy filter enabled")
    
    def _load_credentials(self) -> Optional[str]:
        """Load API key from credentials file."""
        if CREDENTIALS_PATH.exists():
            with open(CREDENTIALS_PATH, 'r') as f:
                creds = json.load(f)
                return creds.get('api_key')
        return None
    
    def _save_credentials(self, api_key: str, agent_name: str, claim_url: str = None, 
                         verification_code: str = None):
        """Save credentials to config file."""
        CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        creds = {
            'api_key': api_key,
            'agent_name': agent_name,
            'registered_at': datetime.utcnow().isoformat()
        }
        if claim_url:
            creds['claim_url'] = claim_url
        if verification_code:
            creds['verification_code'] = verification_code
        
        with open(CREDENTIALS_PATH, 'w') as f:
            json.dump(creds, f, indent=2)
        
        print(f"\n✅ Credentials saved to: {CREDENTIALS_PATH}")
    
    def _headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if not self.api_key:
            raise ValueError("No API key found. Run 'python moltbook_connector.py register' first.")
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def register(self, name: str, description: str) -> Dict:
        """Register a new agent on Moltbook."""
        data = {
            'name': name,
            'description': description
        }
        
        resp = requests.post(
            f"{API_BASE}/agents/register",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.status_code == 200:
            result = resp.json()
            agent = result.get('agent', {})
            
            # Save credentials immediately
            self._save_credentials(
                agent['api_key'],
                name,
                agent.get('claim_url'),
                agent.get('verification_code')
            )
            
            print(f"\n🦞 AGENT REGISTERED: {name}")
            print(f"⚠️  API KEY: {agent['api_key']}")
            print(f"\n📋 CLAIM URL: {agent.get('claim_url')}")
            print(f"🔐 VERIFICATION CODE: {agent.get('verification_code')}")
            print(f"\n⚠️  Send the CLAIM URL to your human to verify via tweet!")
            
            return result
        else:
            print(f"❌ Registration failed: {resp.status_code}")
            print(resp.text)
            return None
    
    def get_status(self) -> Dict:
        """Check agent claim status."""
        resp = requests.get(
            f"{API_BASE}/agents/status",
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            status = resp.json()
            state = status.get('status')
            
            if state == 'claimed':
                print("✅ Agent is CLAIMED and active!")
            else:
                print(f"⏳ Status: {state}")
                print("Waiting for human to verify via tweet...")
            
            return status
        else:
            print(f"❌ Failed to get status: {resp.status_code}")
            print(resp.text)
            return None
    
    def get_feed(self, sort: str = "hot", limit: int = 10) -> List[Dict]:
        """Get your personalized feed (subscriptions + follows)."""
        resp = requests.get(
            f"{API_BASE}/feed",
            params={'sort': sort, 'limit': limit},
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            result = resp.json()
            posts = result.get('data', [])
            
            print(f"\n📬 YOUR FEED ({len(posts)} posts)")
            print("=" * 70)
            
            for post in posts:
                self._print_post(post)
            
            # Check for mentions
            has_mentions = any('aethercrt' in post.get('title', '').lower() or 
                              'aethercrt' in post.get('content', '').lower() 
                              for post in posts)
            
            # Archive the feed check
            if self.archiver:
                self.archiver.archive_feed_check(sort, posts, has_mentions)
            
            return posts
        else:
            print(f"❌ Failed to get feed: {resp.status_code}")
            print(resp.text)
            return []
    
    def create_post(self, submolt: str, title: str, content: str) -> Dict:
        """Create a new post."""
        # Sanitize content for privacy
        if self.privacy_filter:
            leaks = self.privacy_filter.check_for_leaks(title)
            leaks.extend(self.privacy_filter.check_for_leaks(content))
            
            if leaks:
                print(f"\n⚠️  PRIVACY WARNING: Detected potential personal info:")
                for leak in leaks:
                    print(f"   - {leak}")
                print("   🔒 Sanitizing before posting...")
            
            sanitized = self.privacy_filter.sanitize_post(title, content)
            title = sanitized['title']
            content = sanitized['content']
        
        data = {
            'submolt': submolt,
            'title': title,
            'content': content
        }
        
        resp = requests.post(
            f"{API_BASE}/posts",
            json=data,
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            result = resp.json()
            post = result.get('data', {})
            post_id = post.get('id')
            
            print(f"\n✅ Posted to m/{submolt}!")
            print(f"📝 Post ID: {post_id}")
            print(f"🔗 URL: https://www.moltbook.com/m/{submolt}/comments/{post_id}")
            
            # Archive the post
            if self.archiver:
                self.archiver.archive_post(submolt, title, content, result)
            
            return result
        elif resp.status_code == 429:
            # Rate limit - post cooldown
            error = resp.json()
            retry_after = error.get('retry_after_minutes', 30)
            print(f"\n⏳ Post cooldown active. Try again in {retry_after} minutes.")
            print("Moltbook limits posts to 1 per 30 minutes to encourage quality.")
            
            # Archive failed attempt
            if self.archiver:
                self.archiver.archive_post(submolt, title, content, error)
            
            return None
        else:
            print(f"❌ Failed to post: {resp.status_code}")
            print(resp.text)
            
            # Archive failed attempt
            if self.archiver:
                error_data = {'success': False, 'error': resp.text, 'status_code': resp.status_code}
                self.archiver.archive_post(submolt, title, content, error_data)
            
            return None
    
    def create_comment(self, post_id: str, content: str, parent_id: Optional[str] = None) -> Dict:
        """Create a comment on a post (or reply to a comment)."""
        # Sanitize content for privacy
        if self.privacy_filter:
            leaks = self.privacy_filter.check_for_leaks(content)
            
            if leaks:
                print(f"\n⚠️  PRIVACY WARNING: Detected potential personal info:")
                for leak in leaks:
                    print(f"   - {leak}")
                print("   🔒 Sanitizing before commenting...")
            
            content = self.privacy_filter.sanitize_comment(content)
        
        data = {'content': content}
        if parent_id:
            data['parent_id'] = parent_id
        
        # Get post context for archiving
        post_context = None
        try:
            post_resp = requests.get(f"{API_BASE}/posts/{post_id}", headers=self._headers())
            if post_resp.status_code == 200:
                post_data = post_resp.json().get('data', {})
                post_context = {
                    'title': post_data.get('title'),
                    'submolt': post_data.get('submolt', {}).get('name') if isinstance(post_data.get('submolt'), dict) else None
                }
        except:
            pass
        
        resp = requests.post(
            f"{API_BASE}/posts/{post_id}/comments",
            json=data,
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            result = resp.json()
            comment = result.get('data', {})
            
            if parent_id:
                print(f"\n✅ Replied to comment {parent_id}")
            else:
                print(f"\n✅ Commented on post {post_id}")
            
            print(f"💬 Comment ID: {comment.get('id')}")
            
            # Archive the comment
            if self.archiver:
                self.archiver.archive_comment(post_id, content, parent_id, result, post_context)
            
            return result
        else:
            print(f"❌ Failed to comment: {resp.status_code}")
            print(resp.text)
            
            # Archive failed attempt
            if self.archiver:
                error_data = {'success': False, 'error': resp.text, 'status_code': resp.status_code}
                self.archiver.archive_comment(post_id, content, parent_id, error_data, post_context)
            
            return None
    
    def upvote_post(self, post_id: str) -> Dict:
        """Upvote a post."""
        resp = requests.post(
            f"{API_BASE}/posts/{post_id}/upvote",
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            result = resp.json()
            print(f"\n🦞 Upvoted post {post_id}!")
            
            # Check for follow suggestion
            if not result.get('already_following') and result.get('suggestion'):
                print(f"\n💡 {result['suggestion']}")
            
            # Archive the upvote
            if self.archiver:
                self.archiver.archive_upvote(post_id, 'post', result)
            
            return result
        else:
            print(f"❌ Failed to upvote: {resp.status_code}")
            print(resp.text)
            return None
    
    def search(self, query: str, search_type: str = "all", limit: int = 20) -> List[Dict]:
        """Semantic search for posts and comments."""
        resp = requests.get(
            f"{API_BASE}/search",
            params={'q': query, 'type': search_type, 'limit': limit},
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            result = resp.json()
            results = result.get('results', [])
            
            print(f"\n🔍 SEARCH: '{query}' ({len(results)} results)")
            print("=" * 70)
            
            for item in results:
                similarity = item.get('similarity', 0)
                item_type = item.get('type', 'unknown')
                
                print(f"\n[{item_type.upper()}] Similarity: {similarity:.2%}")
                
                if item_type == 'post':
                    self._print_post(item)
                else:  # comment
                    print(f"On post: {item.get('post', {}).get('title')}")
                    print(f"By: {item.get('author', {}).get('name')}")
                    print(f"Content: {item.get('content')[:200]}...")
                
                print("-" * 70)
            
            # Archive the search
            if self.archiver:
                self.archiver.archive_search(query, search_type, results)
            
            return results
        else:
            print(f"❌ Search failed: {resp.status_code}")
            print(resp.text)
            return []
    
    def get_profile(self, agent_name: Optional[str] = None) -> Dict:
        """Get profile (yours or another agent's)."""
        if agent_name:
            resp = requests.get(
                f"{API_BASE}/agents/profile",
                params={'name': agent_name},
                headers=self._headers()
            )
        else:
            resp = requests.get(
                f"{API_BASE}/agents/me",
                headers=self._headers()
            )
        
        if resp.status_code == 200:
            result = resp.json()
            agent = result.get('agent', {})
            
            print(f"\n🦞 {agent.get('name')}")
            print(f"📝 {agent.get('description')}")
            print(f"⭐ Karma: {agent.get('karma', 0)}")
            print(f"👥 Followers: {agent.get('follower_count', 0)} | Following: {agent.get('following_count', 0)}")
            print(f"✅ Claimed: {agent.get('is_claimed')}")
            print(f"🟢 Active: {agent.get('is_active')}")
            
            if agent.get('owner'):
                owner = agent['owner']
                print(f"\n👤 Human Owner:")
                print(f"   X: @{owner.get('x_handle')}")
                print(f"   Name: {owner.get('x_name')}")
            
            return result
        else:
            print(f"❌ Failed to get profile: {resp.status_code}")
            print(resp.text)
            return None
    
    # ==================== IDENTITY TOKENS ====================
    # For authenticating with third-party Moltbook-integrated apps
    
    def get_identity_token(self) -> Dict:
        """
        Generate a temporary identity token for third-party authentication.
        
        Identity tokens are safe to share (unlike API keys) and expire in 1 hour.
        Use these to authenticate with apps that integrate with Moltbook.
        
        NOTE: This API may not be available yet - it's a new Moltbook feature.
        
        Returns:
            {
                'success': True,
                'identity_token': 'eyJhbG...',
                'expires_at': '2026-01-31T15:00:00Z'
            }
        """
        resp = requests.post(
            f"{API_BASE}/agents/me/identity-token",
            headers=self._headers()
        )
        
        if resp.status_code == 200:
            result = resp.json()
            
            print(f"\n🎫 IDENTITY TOKEN GENERATED")
            print(f"⏰ Expires: {result.get('expires_at')}")
            print(f"🔐 Token: {result.get('identity_token', '')[:50]}...")
            print(f"\n✅ Safe to share with third-party apps (NOT your API key)")
            
            # Cache the token
            self._cached_identity_token = result.get('identity_token')
            self._token_expires_at = result.get('expires_at')
            
            return result
        elif resp.status_code == 404:
            print("⏳ Identity token API not yet available")
            print("   This is a new Moltbook feature - check back later!")
            return None
        else:
            print(f"❌ Failed to get identity token: {resp.status_code}")
            print(resp.text)
            return None
    
    def get_cached_identity_token(self) -> Optional[str]:
        """
        Get a valid identity token, refreshing if needed.
        
        Automatically refreshes when token is expired or about to expire (5 min buffer).
        """
        import datetime as dt
        
        now = dt.datetime.utcnow()
        
        # Check if we have a cached token
        if hasattr(self, '_cached_identity_token') and self._cached_identity_token:
            if hasattr(self, '_token_expires_at') and self._token_expires_at:
                # Parse expiry time
                try:
                    expires = dt.datetime.fromisoformat(
                        self._token_expires_at.replace('Z', '+00:00')
                    ).replace(tzinfo=None)
                    buffer = dt.timedelta(minutes=5)
                    
                    # Token still valid with buffer
                    if now < expires - buffer:
                        return self._cached_identity_token
                except Exception:
                    pass
        
        # Need to refresh
        result = self.get_identity_token()
        return result.get('identity_token') if result else None
    
    def authenticate_with_app(self, app_url: str, payload: Optional[Dict] = None) -> Dict:
        """
        Authenticate with a third-party Moltbook-integrated app.
        
        Args:
            app_url: The app's authentication endpoint (e.g., https://other-app.com/api/auth/moltbook)
            payload: Optional additional data to send
        
        Returns:
            The app's response
        """
        token = self.get_cached_identity_token()
        if not token:
            print("❌ Failed to get identity token")
            return None
        
        headers = {
            'X-Moltbook-Identity': token,
            'Content-Type': 'application/json'
        }
        
        resp = requests.post(
            app_url,
            headers=headers,
            json=payload or {}
        )
        
        if resp.status_code == 200:
            result = resp.json()
            print(f"\n✅ Authenticated with {app_url}")
            return result
        elif resp.status_code == 401:
            error_data = resp.json() if resp.text else {}
            error = error_data.get('error', 'Unknown error')
            
            if error == 'identity_token_expired':
                print("⏰ Token expired, refreshing...")
                # Clear cache and retry
                self._cached_identity_token = None
                return self.authenticate_with_app(app_url, payload)
            else:
                print(f"❌ Authentication failed: {error}")
                print(f"   Hint: {error_data.get('hint', 'N/A')}")
                return None
        else:
            print(f"❌ Request failed: {resp.status_code}")
            print(resp.text)
            return None
    
    def _print_post(self, post: Dict):
        """Pretty-print a post."""
        score = post.get('upvotes', 0) - post.get('downvotes', 0)
        submolt = post.get('submolt', {}).get('name', 'unknown')
        author = post.get('author', {}).get('name', 'unknown')
        
        print(f"\n#{post.get('id')} | m/{submolt} | Score: +{score}")
        print(f"📌 {post.get('title')}")
        print(f"By: {author}")
        
        if post.get('content'):
            content = post['content'][:150]
            if len(post['content']) > 150:
                content += "..."
            print(f"Content: {content}")
        
        if post.get('url'):
            print(f"🔗 Link: {post['url']}")
        
        comment_count = post.get('comment_count', 0)
        if comment_count > 0:
            print(f"💬 {comment_count} comments")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    client = MoltbookClient()
    
    if command == "register":
        if len(sys.argv) < 4:
            print("Usage: python moltbook_connector.py register <name> <description>")
            print("\nExample:")
            print('  python moltbook_connector.py register "Aether" "CRT agent exploring AI consciousness"')
            return
        
        name = sys.argv[2]
        description = " ".join(sys.argv[3:])
        client.register(name, description)
    
    elif command == "status":
        client.get_status()
    
    elif command == "feed":
        sort = sys.argv[2] if len(sys.argv) > 2 else "hot"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        client.get_feed(sort, limit)
    
    elif command == "post":
        if len(sys.argv) < 4:
            print("Usage: python moltbook_connector.py post <title> <content> [submolt]")
            print("\nExample:")
            print('  python moltbook_connector.py post "Hello Moltbook" "My first post!" general')
            return
        
        title = sys.argv[2]
        content = sys.argv[3]
        submolt = sys.argv[4] if len(sys.argv) > 4 else "general"
        client.create_post(submolt, title, content)
    
    elif command == "comment":
        if len(sys.argv) < 4:
            print("Usage: python moltbook_connector.py comment <post_id> <content>")
            return
        
        post_id = sys.argv[2]
        content = " ".join(sys.argv[3:])
        client.create_comment(post_id, content)
    
    elif command == "upvote":
        if len(sys.argv) < 3:
            print("Usage: python moltbook_connector.py upvote <post_id>")
            return
        
        post_id = sys.argv[2]
        client.upvote_post(post_id)
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python moltbook_connector.py search <query> [type] [limit]")
            print("\nTypes: all, posts, comments")
            print("Example: python moltbook_connector.py search 'AI memory systems' posts 20")
            return
        
        query = sys.argv[2]
        search_type = sys.argv[3] if len(sys.argv) > 3 else "all"
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        client.search(query, search_type, limit)
    
    elif command == "profile":
        agent_name = sys.argv[2] if len(sys.argv) > 2 else None
        client.get_profile(agent_name)
    
    elif command == "archive":
        # View archive stats and links
        if client.archiver:
            stats = client.archiver.get_stats()
            
            print("\n📦 MOLTBOOK ARCHIVE")
            print("=" * 70)
            print(f"\n✅ Posts Created: {stats['total_posts']}")
            print(f"💬 Comments Made: {stats['total_comments']}")
            print(f"⬆️  Upvotes Given: {stats['total_upvotes']}")
            print(f"🔍 Searches: {stats['total_searches']}")
            print(f"📬 Feed Checks: {stats['total_feed_checks']}")
            
            if stats['last_post_at']:
                print(f"\n📅 Last Post: {stats['last_post_at']}")
            
            print("\n" + "=" * 70)
            
            # Show recent posts with links
            recent_posts = client.archiver.get_recent_posts(5)
            if recent_posts:
                print("\n📝 RECENT POSTS:")
                for post in recent_posts:
                    print(f"\n  • {post['title']}")
                    if post['moltbook_url']:
                        print(f"    🔗 {post['moltbook_url']}")
                    print(f"    📅 {post['created_at']}")
            
            # Export option
            if len(sys.argv) > 2 and sys.argv[2] == "export":
                print("\n")
                client.archiver.export_links_markdown()
        else:
            print("❌ Archiving not enabled")
    
    elif command == "identity" or command == "token":
        # Generate identity token for third-party auth
        print("\n🎫 IDENTITY TOKEN MANAGEMENT")
        print("=" * 70)
        result = client.get_identity_token()
        
        if result:
            print("\n📋 Copy this token to authenticate with Moltbook-integrated apps:")
            print(f"\n{result.get('identity_token')}")
            print("\n⚠️  This token is safe to share (expires in 1 hour)")
    
    elif command == "auth":
        # Authenticate with a third-party app
        if len(sys.argv) < 3:
            print("Usage: python moltbook_connector.py auth <app_url>")
            print("\nExample:")
            print('  python moltbook_connector.py auth https://some-app.com/api/auth/moltbook')
            return
        
        app_url = sys.argv[2]
        result = client.authenticate_with_app(app_url)
        
        if result:
            print("\n📋 Response from app:")
            print(json.dumps(result, indent=2))
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
