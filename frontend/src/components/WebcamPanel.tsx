import React, { useState, useEffect, useRef, useCallback } from 'react';

interface CameraInfo {
  index: number;
  name: string;
  width: number;
  height: number;
  fps: number;
}

interface WebcamStatus {
  available_cameras: CameraInfo[];
  current_camera: {
    camera_index: number;
    is_open: boolean;
    is_streaming: boolean;
    frame_count: number;
    width?: number;
    height?: number;
    fps?: number;
  } | null;
  error?: string;
}

interface WebcamPanelProps {
  apiBase?: string;
  defaultCameraIndex?: number;
  defaultFps?: number;
  showControls?: boolean;
  className?: string;
  onSnapshot?: (imageData: string) => void;
}

export const WebcamPanel: React.FC<WebcamPanelProps> = ({
  apiBase = '',
  defaultCameraIndex = 0,
  defaultFps = 15,
  showControls = true,
  className = '',
  onSnapshot,
}) => {
  const [status, setStatus] = useState<WebcamStatus | null>(null);
  const [selectedCamera, setSelectedCamera] = useState(defaultCameraIndex);
  const [fps, setFps] = useState(defaultFps);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSnapshot, setLastSnapshot] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Fetch webcam status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/webcam/status`);
      const data = await res.json();
      setStatus(data);
      if (data.error) {
        setError(data.error);
      }
    } catch (err) {
      setError(`Failed to get webcam status: ${err}`);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Start streaming
  const startStream = useCallback(() => {
    setIsStreaming(true);
    setError(null);
    // The img src will handle the actual streaming
  }, []);

  // Stop streaming
  const stopStream = useCallback(async () => {
    setIsStreaming(false);
    if (imgRef.current) {
      imgRef.current.src = '';
    }
    // Close webcam on server
    try {
      await fetch(`${apiBase}/api/webcam/close`, { method: 'POST' });
    } catch (err) {
      console.warn('Failed to close webcam:', err);
    }
  }, [apiBase]);

  // Capture snapshot
  const captureSnapshot = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(
        `${apiBase}/api/webcam/snapshot/base64?camera_index=${selectedCamera}`
      );
      const data = await res.json();
      if (data.success && data.image) {
        const imageUrl = `data:image/jpeg;base64,${data.image}`;
        setLastSnapshot(imageUrl);
        onSnapshot?.(imageUrl);
      } else {
        setError(data.error || 'Failed to capture snapshot');
      }
    } catch (err) {
      setError(`Snapshot error: ${err}`);
    } finally {
      setIsLoading(false);
    }
  }, [apiBase, selectedCamera, onSnapshot]);

  // Stream URL
  const streamUrl = `${apiBase}/api/webcam/stream?camera_index=${selectedCamera}&fps=${fps}`;

  return (
    <div className={`webcam-panel ${className}`} style={styles.container}>
      <div style={styles.header}>
        <span style={styles.title}>📹 Webcam</span>
        {status && status.available_cameras.length > 0 && (
          <span style={styles.badge}>
            {status.available_cameras.length} camera{status.available_cameras.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {error && (
        <div style={styles.error}>
          ⚠️ {error}
          <button onClick={() => setError(null)} style={styles.dismissBtn}>×</button>
        </div>
      )}

      {showControls && (
        <div style={styles.controls}>
          {status && status.available_cameras.length > 0 && (
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(Number(e.target.value))}
              style={styles.select}
              disabled={isStreaming}
            >
              {status.available_cameras.map((cam) => (
                <option key={cam.index} value={cam.index}>
                  {cam.name} ({cam.width}x{cam.height})
                </option>
              ))}
            </select>
          )}

          <div style={styles.fpsControl}>
            <label style={styles.label}>FPS:</label>
            <input
              type="range"
              min="1"
              max="30"
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
              style={styles.slider}
              disabled={isStreaming}
            />
            <span style={styles.fpsValue}>{fps}</span>
          </div>

          <div style={styles.buttonGroup}>
            {!isStreaming ? (
              <button onClick={startStream} style={styles.startBtn}>
                ▶️ Start
              </button>
            ) : (
              <button onClick={stopStream} style={styles.stopBtn}>
                ⏹️ Stop
              </button>
            )}
            <button
              onClick={captureSnapshot}
              style={styles.snapshotBtn}
              disabled={isLoading}
            >
              📷 {isLoading ? '...' : 'Snap'}
            </button>
            <button onClick={fetchStatus} style={styles.refreshBtn}>
              🔄
            </button>
          </div>
        </div>
      )}

      <div style={styles.videoContainer}>
        {isStreaming ? (
          <img
            ref={imgRef}
            src={streamUrl}
            alt="Webcam stream"
            style={styles.video}
            onError={() => {
              setError('Stream connection lost');
              setIsStreaming(false);
            }}
          />
        ) : lastSnapshot ? (
          <img src={lastSnapshot} alt="Last snapshot" style={styles.video} />
        ) : (
          <div style={styles.placeholder}>
            <span style={styles.placeholderIcon}>📹</span>
            <span style={styles.placeholderText}>
              {status?.available_cameras.length === 0
                ? 'No cameras detected'
                : 'Click Start to begin streaming'}
            </span>
          </div>
        )}
      </div>

      {status?.current_camera && (
        <div style={styles.stats}>
          <span>Frames: {status.current_camera.frame_count}</span>
          {status.current_camera.width && (
            <span>
              {status.current_camera.width}x{status.current_camera.height}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
    borderRadius: '12px',
    padding: '16px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    color: '#e0e0e0',
    maxWidth: '100%',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '12px',
  },
  title: {
    fontSize: '16px',
    fontWeight: 600,
  },
  badge: {
    background: 'rgba(99, 102, 241, 0.2)',
    color: '#818cf8',
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '12px',
  },
  error: {
    background: 'rgba(239, 68, 68, 0.15)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '8px',
    padding: '8px 12px',
    marginBottom: '12px',
    fontSize: '13px',
    color: '#fca5a5',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dismissBtn: {
    background: 'none',
    border: 'none',
    color: '#fca5a5',
    cursor: 'pointer',
    fontSize: '16px',
    padding: '0 4px',
  },
  controls: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    marginBottom: '12px',
  },
  select: {
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '6px',
    padding: '8px 12px',
    color: '#e0e0e0',
    fontSize: '13px',
    cursor: 'pointer',
  },
  fpsControl: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  label: {
    fontSize: '13px',
    color: '#a0a0a0',
  },
  slider: {
    flex: 1,
    accentColor: '#6366f1',
  },
  fpsValue: {
    minWidth: '24px',
    fontSize: '13px',
    color: '#818cf8',
  },
  buttonGroup: {
    display: 'flex',
    gap: '8px',
  },
  startBtn: {
    flex: 1,
    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 16px',
    color: 'white',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
  },
  stopBtn: {
    flex: 1,
    background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 16px',
    color: 'white',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
  },
  snapshotBtn: {
    background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 16px',
    color: 'white',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
  },
  refreshBtn: {
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '6px',
    padding: '8px 12px',
    color: '#e0e0e0',
    cursor: 'pointer',
    fontSize: '13px',
  },
  videoContainer: {
    position: 'relative',
    width: '100%',
    aspectRatio: '4/3',
    background: '#0a0a0f',
    borderRadius: '8px',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  video: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },
  placeholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    color: '#6b7280',
  },
  placeholderIcon: {
    fontSize: '48px',
    opacity: 0.3,
  },
  placeholderText: {
    fontSize: '13px',
    textAlign: 'center',
  },
  stats: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '8px',
    fontSize: '11px',
    color: '#6b7280',
  },
};

export default WebcamPanel;
