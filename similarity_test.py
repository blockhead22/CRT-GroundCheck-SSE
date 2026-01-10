import sys
sys.path.insert(0, "D:/AI_round2")
import numpy as np
from personal_agent.crt_core import encode_vector

# Test similarity between Microsoft and Amazon statements
v1 = encode_vector("I work at Microsoft")
v2 = encode_vector("I work at Amazon")

similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
drift = 1.0 - similarity

print(f"Similarity: {similarity:.4f}")
print(f"Drift: {drift:.4f}")
print(f"theta_contra = 0.28")
print(f"Would detect: {drift > 0.28}")
