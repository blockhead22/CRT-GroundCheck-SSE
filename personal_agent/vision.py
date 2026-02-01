"""
AI Vision module for CRT system.

Provides:
- Object detection and description via vision LLMs
- Face detection via OpenCV
- Face recognition via face_recognition library
- Integration with Ollama vision models
"""

import cv2
import numpy as np
import base64
import time
import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import face_recognition (optional dependency)
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning("[VISION] face_recognition not installed - facial recognition disabled")


@dataclass
class DetectedFace:
    """A detected face in an image."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0
    name: Optional[str] = None  # If recognized
    encoding: Optional[np.ndarray] = None


@dataclass 
class DetectedObject:
    """A detected object in an image."""
    label: str
    confidence: float
    x: int
    y: int
    width: int
    height: int


@dataclass
class VisionResult:
    """Result from vision analysis."""
    description: Optional[str] = None
    faces: List[DetectedFace] = field(default_factory=list)
    objects: List[DetectedObject] = field(default_factory=list)
    face_count: int = 0
    has_person: bool = False
    timestamp: float = field(default_factory=time.time)
    processing_time_ms: float = 0
    error: Optional[str] = None


class FaceDatabase:
    """
    Simple face recognition database.
    Stores face encodings with names for recognition.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.encodings_file = self.db_path / "face_encodings.json"
        self.faces_dir = self.db_path / "faces"
        self.faces_dir.mkdir(exist_ok=True)
        
        self._encodings: Dict[str, List[List[float]]] = {}
        self._load()
    
    def _load(self) -> None:
        """Load saved face encodings."""
        if self.encodings_file.exists():
            try:
                with open(self.encodings_file, 'r') as f:
                    self._encodings = json.load(f)
                logger.info(f"[FACES] Loaded {len(self._encodings)} known faces")
            except Exception as e:
                logger.error(f"[FACES] Failed to load encodings: {e}")
                self._encodings = {}
    
    def _save(self) -> None:
        """Save face encodings to disk."""
        try:
            with open(self.encodings_file, 'w') as f:
                json.dump(self._encodings, f)
        except Exception as e:
            logger.error(f"[FACES] Failed to save encodings: {e}")
    
    def add_face(self, name: str, image: np.ndarray) -> bool:
        """
        Add a face to the database.
        
        Args:
            name: Name to associate with the face
            image: BGR image containing the face
            
        Returns:
            True if face was added successfully
        """
        if not FACE_RECOGNITION_AVAILABLE:
            logger.error("[FACES] face_recognition not available")
            return False
        
        # Convert BGR to RGB for face_recognition
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Find faces and get encodings
        locations = face_recognition.face_locations(rgb)
        if not locations:
            logger.warning(f"[FACES] No face found in image for {name}")
            return False
        
        encodings = face_recognition.face_encodings(rgb, locations)
        if not encodings:
            logger.warning(f"[FACES] Could not encode face for {name}")
            return False
        
        # Store encoding
        if name not in self._encodings:
            self._encodings[name] = []
        
        # Add the encoding (as list for JSON serialization)
        self._encodings[name].append(encodings[0].tolist())
        self._save()
        
        # Save face image for reference
        face_path = self.faces_dir / f"{name}_{len(self._encodings[name])}.jpg"
        top, right, bottom, left = locations[0]
        face_img = image[top:bottom, left:right]
        cv2.imwrite(str(face_path), face_img)
        
        logger.info(f"[FACES] Added face for {name} (total: {len(self._encodings[name])} samples)")
        return True
    
    def recognize(self, image: np.ndarray, tolerance: float = 0.6) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        Recognize faces in an image.
        
        Args:
            image: BGR image
            tolerance: How strict the matching should be (lower = stricter)
            
        Returns:
            List of (name, confidence, (top, right, bottom, left)) tuples
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return []
        
        if not self._encodings:
            return []
        
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        
        if not locations:
            return []
        
        encodings = face_recognition.face_encodings(rgb, locations)
        results = []
        
        # Build known encodings array
        known_names = []
        known_encodings = []
        for name, enc_list in self._encodings.items():
            for enc in enc_list:
                known_names.append(name)
                known_encodings.append(np.array(enc))
        
        for face_encoding, location in zip(encodings, locations):
            # Compare to known faces
            distances = face_recognition.face_distance(known_encodings, face_encoding)
            
            if len(distances) > 0:
                best_idx = np.argmin(distances)
                best_distance = distances[best_idx]
                
                if best_distance <= tolerance:
                    name = known_names[best_idx]
                    confidence = 1.0 - best_distance
                    results.append((name, confidence, location))
                else:
                    results.append(("Unknown", 0.0, location))
            else:
                results.append(("Unknown", 0.0, location))
        
        return results
    
    def list_known_faces(self) -> List[str]:
        """List all known face names."""
        return list(self._encodings.keys())
    
    def remove_face(self, name: str) -> bool:
        """Remove a face from the database."""
        if name in self._encodings:
            del self._encodings[name]
            self._save()
            return True
        return False


class VisionAI:
    """
    Main vision AI class combining multiple vision capabilities.
    """
    
    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        vision_model: str = "llava",
        face_db_path: str = "data/faces",
    ):
        self.ollama_host = ollama_host
        self.vision_model = vision_model
        self.face_db = FaceDatabase(face_db_path)
        
        # Load OpenCV face detector (Haar cascade - fast)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Try to load DNN face detector (more accurate)
        self._dnn_net = None
        try:
            model_path = Path(__file__).parent / "models"
            prototxt = model_path / "deploy.prototxt"
            caffemodel = model_path / "res10_300x300_ssd_iter_140000.caffemodel"
            if prototxt.exists() and caffemodel.exists():
                self._dnn_net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
                logger.info("[VISION] DNN face detector loaded")
        except Exception as e:
            logger.debug(f"[VISION] DNN face detector not available: {e}")
    
    def describe_image(
        self,
        image: np.ndarray,
        prompt: str = "Describe what you see in this image in detail.",
        max_tokens: int = 500,
    ) -> str:
        """
        Use vision LLM to describe an image.
        
        Args:
            image: BGR image (numpy array)
            prompt: What to ask about the image
            max_tokens: Maximum response length
            
        Returns:
            Description from the vision model
        """
        import requests
        
        # Encode image to base64
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                    }
                },
                timeout=60,
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
            else:
                logger.error(f"[VISION] Ollama error: {response.status_code}")
                return f"Error: Vision model returned {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to Ollama. Is it running?"
        except Exception as e:
            logger.error(f"[VISION] Description error: {e}")
            return f"Error: {str(e)}"
    
    def detect_faces_haar(self, image: np.ndarray) -> List[DetectedFace]:
        """Detect faces using Haar cascade (fast but less accurate)."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )
        
        results = []
        for (x, y, w, h) in faces:
            results.append(DetectedFace(
                x=int(x), y=int(y), width=int(w), height=int(h),
                confidence=0.8,  # Haar doesn't give confidence
            ))
        
        return results
    
    def detect_faces_dnn(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[DetectedFace]:
        """Detect faces using DNN (more accurate)."""
        if self._dnn_net is None:
            return self.detect_faces_haar(image)
        
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(image, (300, 300)), 1.0, (300, 300),
            (104.0, 177.0, 123.0)
        )
        
        self._dnn_net.setInput(blob)
        detections = self._dnn_net.forward()
        
        results = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                
                results.append(DetectedFace(
                    x=int(x1), y=int(y1),
                    width=int(x2 - x1), height=int(y2 - y1),
                    confidence=float(confidence),
                ))
        
        return results
    
    def detect_and_recognize_faces(
        self,
        image: np.ndarray,
        use_recognition: bool = True,
    ) -> List[DetectedFace]:
        """
        Detect faces and optionally recognize them.
        
        Args:
            image: BGR image
            use_recognition: Whether to attempt recognition
            
        Returns:
            List of detected (and optionally recognized) faces
        """
        # First detect faces
        faces = self.detect_faces_dnn(image) if self._dnn_net else self.detect_faces_haar(image)
        
        if not faces:
            return []
        
        # If recognition is enabled and available
        if use_recognition and FACE_RECOGNITION_AVAILABLE and self.face_db._encodings:
            recognized = self.face_db.recognize(image)
            
            # Match recognized faces to detected faces
            for rec_name, rec_conf, (top, right, bottom, left) in recognized:
                rec_x, rec_y = left, top
                rec_w, rec_h = right - left, bottom - top
                
                # Find matching detection
                for face in faces:
                    # Check overlap
                    if (abs(face.x - rec_x) < 50 and abs(face.y - rec_y) < 50):
                        face.name = rec_name
                        if rec_name != "Unknown":
                            face.confidence = rec_conf
                        break
        
        return faces
    
    def analyze_frame(
        self,
        image: np.ndarray,
        describe: bool = True,
        detect_faces: bool = True,
        recognize_faces: bool = True,
        description_prompt: str = "Describe what you see in this image briefly.",
    ) -> VisionResult:
        """
        Full analysis of a frame.
        
        Args:
            image: BGR image
            describe: Whether to get LLM description
            detect_faces: Whether to detect faces
            recognize_faces: Whether to recognize faces
            description_prompt: Prompt for description
            
        Returns:
            VisionResult with all analysis
        """
        start_time = time.time()
        result = VisionResult()
        
        try:
            # Face detection/recognition
            if detect_faces:
                result.faces = self.detect_and_recognize_faces(image, recognize_faces)
                result.face_count = len(result.faces)
                result.has_person = result.face_count > 0
            
            # Vision description
            if describe:
                result.description = self.describe_image(image, description_prompt)
            
        except Exception as e:
            logger.error(f"[VISION] Analysis error: {e}")
            result.error = str(e)
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result
    
    def draw_detections(
        self,
        image: np.ndarray,
        faces: List[DetectedFace],
        draw_labels: bool = True,
    ) -> np.ndarray:
        """
        Draw face detections on image.
        
        Returns a copy of the image with bounding boxes.
        """
        output = image.copy()
        
        for face in faces:
            color = (0, 255, 0) if face.name and face.name != "Unknown" else (0, 165, 255)
            
            # Draw rectangle
            cv2.rectangle(
                output,
                (face.x, face.y),
                (face.x + face.width, face.y + face.height),
                color, 2
            )
            
            # Draw label
            if draw_labels:
                label = face.name or "Face"
                if face.confidence > 0:
                    label += f" ({face.confidence:.0%})"
                
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                cv2.rectangle(
                    output,
                    (face.x, face.y - label_size[1] - 10),
                    (face.x + label_size[0] + 6, face.y),
                    color, -1
                )
                cv2.putText(
                    output, label,
                    (face.x + 3, face.y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
                )
        
        return output


# Global instance
_vision_instance: Optional[VisionAI] = None


def get_vision_ai(
    ollama_host: str = "http://localhost:11434",
    vision_model: str = "llava",
    face_db_path: str = "data/faces",
) -> VisionAI:
    """Get or create the global VisionAI instance."""
    global _vision_instance
    
    if _vision_instance is None:
        _vision_instance = VisionAI(
            ollama_host=ollama_host,
            vision_model=vision_model,
            face_db_path=face_db_path,
        )
    
    return _vision_instance
