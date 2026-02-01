import React, { useState, useCallback } from 'react';
import { WebcamPanel } from '../components/WebcamPanel';

interface WebcamPageProps {
  apiBase?: string;
}

export const WebcamPage: React.FC<WebcamPageProps> = ({ apiBase = '' }) => {
  const [snapshots, setSnapshots] = useState<string[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null);

  const handleSnapshot = useCallback((imageData: string) => {
    setSnapshots(prev => [imageData, ...prev].slice(0, 12)); // Keep last 12
  }, []);

  const clearSnapshots = useCallback(() => {
    setSnapshots([]);
    setSelectedSnapshot(null);
  }, []);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>📹 Webcam</h1>
        <p style={styles.subtitle}>Live camera feed from your Logitech webcam</p>
      </div>

      <div style={styles.content}>
        <div style={styles.mainColumn}>
          <WebcamPanel
            apiBase={apiBase}
            showControls={true}
            onSnapshot={handleSnapshot}
            className="webcam-main"
          />

          <div style={styles.infoCard}>
            <h3 style={styles.cardTitle}>🔧 Camera Setup</h3>
            <ul style={styles.infoList}>
              <li>Uses OpenCV to capture from USB webcam</li>
              <li>MJPEG streaming for real-time video</li>
              <li>Adjustable FPS (1-30)</li>
              <li>Snapshot capture with history</li>
            </ul>
          </div>
        </div>

        <div style={styles.snapshotColumn}>
          <div style={styles.snapshotHeader}>
            <h3 style={styles.cardTitle}>📸 Snapshots</h3>
            {snapshots.length > 0 && (
              <button onClick={clearSnapshots} style={styles.clearBtn}>
                Clear all
              </button>
            )}
          </div>

          {snapshots.length === 0 ? (
            <div style={styles.emptySnapshots}>
              <span style={styles.emptyIcon}>📷</span>
              <p>No snapshots yet</p>
              <p style={styles.emptyHint}>Click "Snap" to capture images</p>
            </div>
          ) : (
            <div style={styles.snapshotGrid}>
              {snapshots.map((snap, index) => (
                <div
                  key={index}
                  style={{
                    ...styles.snapshotThumb,
                    ...(selectedSnapshot === snap ? styles.snapshotSelected : {}),
                  }}
                  onClick={() => setSelectedSnapshot(selectedSnapshot === snap ? null : snap)}
                >
                  <img src={snap} alt={`Snapshot ${index + 1}`} style={styles.thumbImg} />
                  <span style={styles.snapIndex}>{index + 1}</span>
                </div>
              ))}
            </div>
          )}

          {selectedSnapshot && (
            <div style={styles.previewContainer}>
              <h4 style={styles.previewTitle}>Preview</h4>
              <img src={selectedSnapshot} alt="Selected snapshot" style={styles.previewImg} />
              <div style={styles.previewActions}>
                <a
                  href={selectedSnapshot}
                  download={`snapshot-${Date.now()}.jpg`}
                  style={styles.downloadBtn}
                >
                  💾 Download
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    padding: '24px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  header: {
    marginBottom: '24px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    color: '#e0e0e0',
    margin: 0,
  },
  subtitle: {
    fontSize: '14px',
    color: '#888',
    marginTop: '4px',
  },
  content: {
    display: 'grid',
    gridTemplateColumns: '1fr 320px',
    gap: '24px',
  },
  mainColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  snapshotColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  snapshotHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#e0e0e0',
    margin: 0,
  },
  clearBtn: {
    background: 'none',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '4px',
    padding: '4px 8px',
    color: '#888',
    cursor: 'pointer',
    fontSize: '12px',
  },
  infoCard: {
    background: 'rgba(255, 255, 255, 0.03)',
    borderRadius: '12px',
    padding: '16px',
    border: '1px solid rgba(255, 255, 255, 0.06)',
  },
  infoList: {
    margin: '12px 0 0 0',
    paddingLeft: '20px',
    color: '#888',
    fontSize: '13px',
    lineHeight: 1.8,
  },
  emptySnapshots: {
    background: 'rgba(255, 255, 255, 0.03)',
    borderRadius: '12px',
    padding: '32px',
    textAlign: 'center',
    color: '#666',
    border: '1px solid rgba(255, 255, 255, 0.06)',
  },
  emptyIcon: {
    fontSize: '36px',
    opacity: 0.4,
    display: 'block',
    marginBottom: '8px',
  },
  emptyHint: {
    fontSize: '12px',
    color: '#555',
    marginTop: '4px',
  },
  snapshotGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '8px',
  },
  snapshotThumb: {
    position: 'relative',
    aspectRatio: '4/3',
    borderRadius: '8px',
    overflow: 'hidden',
    cursor: 'pointer',
    border: '2px solid transparent',
    transition: 'border-color 0.2s, transform 0.2s',
  },
  snapshotSelected: {
    borderColor: '#6366f1',
    transform: 'scale(1.02)',
  },
  thumbImg: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  snapIndex: {
    position: 'absolute',
    bottom: '4px',
    right: '4px',
    background: 'rgba(0, 0, 0, 0.7)',
    color: '#fff',
    fontSize: '10px',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  previewContainer: {
    background: 'rgba(255, 255, 255, 0.03)',
    borderRadius: '12px',
    padding: '12px',
    border: '1px solid rgba(255, 255, 255, 0.06)',
  },
  previewTitle: {
    fontSize: '12px',
    color: '#888',
    margin: '0 0 8px 0',
  },
  previewImg: {
    width: '100%',
    borderRadius: '8px',
  },
  previewActions: {
    marginTop: '8px',
    display: 'flex',
    justifyContent: 'center',
  },
  downloadBtn: {
    background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
    color: 'white',
    textDecoration: 'none',
    padding: '8px 16px',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: 500,
  },
};

export default WebcamPage;
