"""
Webcam capture module for CRT system.

Provides webcam access for the heartbeat and other components.
Uses OpenCV for capture and supports MJPEG streaming.
"""

import cv2
import time
import threading
import logging
from typing import Optional, Tuple, Generator, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WebcamInfo:
    """Information about a detected webcam."""
    index: int
    name: str
    width: int
    height: int
    fps: float
    is_available: bool


class WebcamCapture:
    """
    Manages webcam capture with thread-safe access.
    
    Supports:
    - Single frame capture
    - MJPEG streaming
    - Multiple camera detection
    - Resolution/FPS configuration
    """
    
    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._is_streaming = False
        self._last_frame: Optional[bytes] = None
        self._last_frame_time: float = 0
        self._frame_count: int = 0
        
    def open(self) -> bool:
        """Open the webcam. Returns True if successful."""
        with self._lock:
            if self._cap is not None:
                return True
            
            try:
                # Try DirectShow on Windows for better compatibility
                self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                
                if not self._cap.isOpened():
                    # Fallback to default backend
                    self._cap = cv2.VideoCapture(self.camera_index)
                
                if not self._cap.isOpened():
                    logger.error(f"[WEBCAM] Failed to open camera {self.camera_index}")
                    self._cap = None
                    return False
                
                # Configure camera
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self._cap.set(cv2.CAP_PROP_FPS, self.fps)
                
                # Read actual settings
                actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
                
                logger.info(f"[WEBCAM] Opened camera {self.camera_index}: {actual_width}x{actual_height} @ {actual_fps}fps")
                return True
                
            except Exception as e:
                logger.error(f"[WEBCAM] Error opening camera: {e}")
                self._cap = None
                return False
    
    def close(self) -> None:
        """Release the webcam."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info(f"[WEBCAM] Camera {self.camera_index} closed")
    
    def is_open(self) -> bool:
        """Check if webcam is open and available."""
        with self._lock:
            return self._cap is not None and self._cap.isOpened()
    
    def capture_frame(self) -> Optional[bytes]:
        """
        Capture a single frame as JPEG bytes.
        
        Returns None if capture fails.
        """
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                if not self.open():
                    return None
            
            try:
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    logger.warning("[WEBCAM] Failed to read frame")
                    return None
                
                # Encode as JPEG
                _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                self._last_frame = jpeg.tobytes()
                self._last_frame_time = time.time()
                self._frame_count += 1
                
                return self._last_frame
                
            except Exception as e:
                logger.error(f"[WEBCAM] Error capturing frame: {e}")
                return None
    
    def capture_frame_base64(self) -> Optional[str]:
        """Capture a frame and return as base64 string."""
        import base64
        frame = self.capture_frame()
        if frame:
            return base64.b64encode(frame).decode('utf-8')
        return None
    
    def generate_mjpeg_stream(self, max_fps: int = 15) -> Generator[bytes, None, None]:
        """
        Generate MJPEG stream for HTTP streaming.
        
        Yields multipart JPEG frames suitable for streaming response.
        """
        frame_interval = 1.0 / max_fps
        self._is_streaming = True
        
        try:
            while self._is_streaming:
                start_time = time.time()
                
                frame = self.capture_frame()
                if frame:
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                    )
                
                # Rate limiting
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                    
        except GeneratorExit:
            self._is_streaming = False
        finally:
            self._is_streaming = False
    
    def stop_streaming(self) -> None:
        """Stop the MJPEG stream."""
        self._is_streaming = False
    
    def get_info(self) -> Dict[str, Any]:
        """Get current webcam info and stats."""
        with self._lock:
            is_open = self._cap is not None and self._cap.isOpened()
            
            info = {
                "camera_index": self.camera_index,
                "is_open": is_open,
                "is_streaming": self._is_streaming,
                "frame_count": self._frame_count,
                "last_frame_age": time.time() - self._last_frame_time if self._last_frame_time > 0 else None,
            }
            
            if is_open and self._cap:
                info["width"] = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                info["height"] = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                info["fps"] = self._cap.get(cv2.CAP_PROP_FPS)
                info["backend"] = self._cap.getBackendName()
            
            return info


def list_available_cameras(max_index: int = 5) -> List[WebcamInfo]:
    """
    Detect available cameras on the system.
    
    Args:
        max_index: Maximum camera index to check (0-based)
    
    Returns:
        List of WebcamInfo for available cameras
    """
    cameras = []
    
    for i in range(max_index):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                
                # Try to get camera name (not always available)
                backend = cap.getBackendName()
                name = f"Camera {i} ({backend})"
                
                cameras.append(WebcamInfo(
                    index=i,
                    name=name,
                    width=width,
                    height=height,
                    fps=fps,
                    is_available=True,
                ))
                cap.release()
            else:
                cap.release()
        except Exception as e:
            logger.debug(f"[WEBCAM] Error checking camera {i}: {e}")
    
    return cameras


# Global webcam instance (singleton pattern)
_webcam_instance: Optional[WebcamCapture] = None
_webcam_lock = threading.Lock()


def get_webcam(camera_index: int = 0, width: int = 640, height: int = 480) -> WebcamCapture:
    """
    Get the global webcam instance.
    
    Creates a new instance if needed or if camera_index changed.
    """
    global _webcam_instance
    
    with _webcam_lock:
        if _webcam_instance is None or _webcam_instance.camera_index != camera_index:
            if _webcam_instance is not None:
                _webcam_instance.close()
            _webcam_instance = WebcamCapture(
                camera_index=camera_index,
                width=width,
                height=height,
            )
        return _webcam_instance


def close_webcam() -> None:
    """Close the global webcam instance."""
    global _webcam_instance
    
    with _webcam_lock:
        if _webcam_instance is not None:
            _webcam_instance.close()
            _webcam_instance = None
