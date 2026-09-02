# Phase 2: Face Identification (Detection + Pretrained Encoding)
**HH Goa 2026 Shortlisting Challenge — Task 3**

---

## 1. Overview & Architecture

Phase 2 builds a reliable, production-grade **Face Detection and Pretrained Face Encoding pipeline**. It accepts any local image, identifies all visible human faces, extracts and saves individual normalized face crops, computes high-dimensional 512-D facial embeddings, and formats the output into clean structured data for downstream integration with Phase 1 (Reverse Image Search) and Phase 3 (Blockchain Verification).

```
Input Image ──► Face Detection (MTCNN) ──► Bounding Boxes [x1, y1, x2, y2]
                                      └──► Face Crop Extraction (160x160)
                                            └──► InceptionResnetV1 (VGGFace2)
                                                  └──► 512-D Normalized Embedding
```

---

## 2. Model Evaluation & Selection Rationale

We evaluated established face detection and recognition frameworks against our operational criteria:

| Solution / Framework | Detection Accuracy | Embedding Quality | Windows / CPU Reliability | Pretrained Availability | Dependencies / Installation | Selected? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MTCNN + InceptionResnetV1 (VGGFace2)** | **High** (3-stage cascaded CNN) | **512-D L2-Normalized** (VGGFace2) | **Exceptional** (Native PyTorch on CPU & CUDA) | **Pretrained weights included** | Pure PyTorch / Torchvision | **YES (Primary)** |
| **OpenCV YuNet + SFace** | High (DNN-based) | 128-D Embedding | High on CPU | ONNX files required | OpenCV DNN | Alternative |
| **face_recognition (dlib)** | Moderate (HOG / CNN) | 128-D Embedding | Low on Windows (requires C++ CMake & MSVC build) | Included | Difficult Windows setup | No |
| **InsightFace (ArcFace)** | Very High | 512-D Embedding | Moderate (complex ONNX / Cython bindings on Windows) | Pretrained | Heavy binary deps | No |
| **MediaPipe Face Mesh** | High (468 landmarks) | Landmarks only (No direct face recognition vector) | High | Included | Google MediaPipe | No |

### Why Selected:
1. **Pretrained Quality**: Inception-ResNet-v1 trained on the VGGFace2 dataset (3.3M+ faces over 9,000 identities) produces discriminative 512-dimensional embeddings that maintain separation across diverse facial angles and lighting.
2. **Zero Training**: Operates 100% out-of-the-box using official pretrained model checkpoints.
3. **Seamless Windows & CPU Execution**: Runs natively via PyTorch on Windows without requiring complex C++ compiler toolchains (CMake/MSVC) or fragile native builds.
4. **Multi-Face Support**: MTCNN reliably extracts and tags multiple faces (`face_01`, `face_02`, etc.) in a single inference pass.

---

## 3. Directory Structure

```
phase2/
├── face_identifier.py      # Core detection and 512-D face encoding pipeline + CLI
├── requirements.txt        # Dependencies: torch, torchvision, facenet-pytorch, pillow, numpy
├── README.md               # Complete architecture, usage, and verification guide
├── output/
│   └── faces/              # Automatically generated extracted face crops
│       ├── face_01.jpg
│       └── face_02.jpg
└── test_images/            # Test images
    ├── single_face.jpg     # Image containing 1 clear face
    ├── multiple_faces.jpg  # Image containing 2 faces
    └── no_face.jpg         # Image containing 0 human faces
```

---

## 4. Setup Instructions

### Prerequisites
- Python 3.9+ (Python 3.11 recommended)
- PyTorch & Torchvision

### Install Dependencies:
```bash
pip install -r phase2/requirements.txt
```

---

## 5. Programmatic API Usage

You can import and call `identify_faces()` directly from Python:

```python
from phase2.face_identifier import identify_faces

# Run face identification on an image
result = identify_faces("phase2/test_images/single_face.jpg")

print(f"Faces found: {result['faces_detected']}")

for face in result["faces"]:
    print(f"Face ID: {face['face_id']}")
    print(f"Bounding Box [x1, y1, x2, y2]: {face['bbox']}")
    print(f"Confidence Score: {face['confidence']}")
    print(f"Saved Crop Path: {face['crop_path']}")
    print(f"Embedding Dimension: {face['embedding_dimension']}")
    print(f"Sample Embedding Values: {face['embedding'][:5]}...")
```

### Return Data Structure:
```json
{
  "image": "phase2/test_images/single_face.jpg",
  "faces_detected": 1,
  "faces": [
    {
      "face_id": "face_01",
      "bbox": [192, 118, 316, 283],
      "confidence": 1.0,
      "crop_path": "phase2/output/faces/face_01.jpg",
      "embedding_dimension": 512,
      "embedding": [0.0633, -0.0334, 0.0016, 0.0240, ...]
    }
  ]
}
```

---

## 6. CLI Usage & Examples

### Test 1: Single Face Image
```bash
python phase2/face_identifier.py --image phase2/test_images/single_face.jpg
```
**Terminal Output:**
```text
========================================
PHASE 2 - FACE IDENTIFICATION
========================================

Input:
phase2/test_images/single_face.jpg

✓ Image validated
✓ Face detection completed

FACE 01
Bounding box: [192, 118, 316, 283]
Confidence: 1.0
Embedding dimension: 512

✓ Face encoding completed

Faces detected: 1

========================================
```

### Test 2: Multiple Faces Image
```bash
python phase2/face_identifier.py --image phase2/test_images/multiple_faces.jpg
```
**Terminal Output:**
```text
========================================
PHASE 2 - FACE IDENTIFICATION
========================================

Input:
phase2/test_images/multiple_faces.jpg

✓ Image validated
✓ Face detection completed

FACE 01
Bounding box: [117, 57, 187, 147]
Confidence: 1.0
Embedding dimension: 512

FACE 02
Bounding box: [465, 58, 529, 144]
Confidence: 0.9998
Embedding dimension: 512

✓ Face encoding completed

Faces detected: 2

========================================
```

### Test 3: No Face Image
```bash
python phase2/face_identifier.py --image phase2/test_images/no_face.jpg
```
**Terminal Output:**
```text
========================================
PHASE 2 - FACE IDENTIFICATION
========================================

Input:
phase2/test_images/no_face.jpg

✓ Image validated
✓ Face detection completed

[NOTICE] No human faces were detected in the input image.

Faces detected: 0

========================================
```

### Test 4: JSON Output Mode
```bash
python phase2/face_identifier.py --image phase2/test_images/single_face.jpg --json
```

---

## 7. Error Handling & Edge Cases

| Condition | Exception | Handling & CLI Behavior |
| :--- | :--- | :--- |
| **Missing Image File** | `ImageNotFoundError` | Clean message `[ERROR: IMAGE NOT FOUND]` with exit code 2. |
| **Corrupt Image** | `InvalidImageError` | Validates PIL headers and exits cleanly with exit code 2. |
| **No Face Detected** | Clean graceful handling | Returns `faces_detected: 0` and `faces: []` without crashing. |
| **Model Failure** | `ModelLoadError` | Clear error reporting missing dependencies with exit code 3. |

---

## 8. Integration Ready for Phase 3

The output from Phase 2 seamlessly connects with the overall pipeline:
1. **Face Scan**: Raw user camera or image input is passed to `identify_faces()`.
2. **Reverse Search**: The cropped face image in `phase2/output/faces/face_01.jpg` is passed directly to `phase1/reverse_search.py` to search Google Lens for matching web content.
3. **Verification & Blockchain**: The 512-D face embedding vector + discovered social media URL are cryptographically hashed and recorded onto the blockchain smart contract in Phase 3.
