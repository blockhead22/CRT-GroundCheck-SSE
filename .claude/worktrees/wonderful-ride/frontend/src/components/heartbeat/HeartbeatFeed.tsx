import React, { useEffect, useState } from 'react';
import './HeartbeatFeed.css';

interface HeartbeatAction {
  action: string;
  success: boolean;
  post_id?: number;
  comment_id?: number;
  title?: string;
  direction?: string;
  error?: string;
  dry_run?: boolean;
}

interface HeartbeatActivity {
  timestamp: number;
  summary: string;
  actions: HeartbeatAction[];
  success: boolean;
}

interface HeartbeatFeedProps {
  threadId?: string;
  limit?: number;
  showTitle?: boolean;
}

export const HeartbeatFeed: React.FC<HeartbeatFeedProps> = ({
  threadId,
  limit = 10,
  showTitle = true
}) => {
  const [activities, setActivities] = useState<HeartbeatActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchActivities = async () => {
      try {
        setLoading(true);
        setError(null);

        const url = threadId
          ? `/api/threads/${threadId}/heartbeat/history?limit=${limit}`
          : `/api/heartbeat/history?limit=${limit}`;

        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Failed to fetch heartbeat activities');
        }

        const data = await response.json();
        setActivities(data.activities || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchActivities();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchActivities, 30000);
    return () => clearInterval(interval);
  }, [threadId, limit]);

  const formatTimestamp = (timestamp: number): string => {
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return `${seconds}s ago`;
  };

  const getActionEmoji = (action: HeartbeatAction): string => {
    if (!action.success) return '❌';
    if (action.dry_run) return '🔍';
    
    switch (action.action) {
      case 'post':
        return '📝';
      case 'comment':
        return '💬';
      case 'vote':
        return action.direction === 'up' ? '👍' : '👎';
      default:
        return '✅';
    }
  };

  const getActionDescription = (action: HeartbeatAction): string => {
    if (!action.success) {
      return `Failed: ${action.error || 'Unknown error'}`;
    }

    const dryRun = action.dry_run ? ' (dry run)' : '';

    switch (action.action) {
      case 'post':
        return `Posted: "${action.title || 'Untitled'}"${dryRun}`;
      case 'comment':
        return `Commented on post #${action.post_id}${dryRun}`;
      case 'vote':
        return `Voted ${action.direction} on post #${action.post_id}${dryRun}`;
      case 'none':
        return 'No action needed';
      default:
        return `Action: ${action.action}${dryRun}`;
    }
  };

  if (loading) {
    return (
      <div className="heartbeat-feed loading">
        <div className="spinner" />
        <p>Loading heartbeat activity...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="heartbeat-feed error">
        <p>Error: {error}</p>
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="heartbeat-feed empty">
        <p>🦞 No heartbeat activity yet</p>
        <p className="hint">The heartbeat loop checks for new activity periodically</p>
      </div>
    );
  }

  return (
    <div className="heartbeat-feed">
      {showTitle && <h3>🦞 Heartbeat Activity</h3>}
      
      <div className="activity-list">
        {activities.map((activity, idx) => (
          <div key={idx} className={`activity-item ${activity.success ? 'success' : 'failure'}`}>
            <div className="activity-header">
              <span className="activity-time">{formatTimestamp(activity.timestamp)}</span>
              <span className="activity-status">
                {activity.success ? '✅' : '❌'}
              </span>
            </div>
            
            {activity.summary && (
              <div className="activity-summary">{activity.summary}</div>
            )}
            
            {activity.actions && activity.actions.length > 0 && (
              <div className="activity-actions">
                {activity.actions.map((action, actionIdx) => (
                  <div key={actionIdx} className="action-badge">
                    <span className="action-emoji">{getActionEmoji(action)}</span>
                    <span className="action-text">{getActionDescription(action)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default HeartbeatFeed;
