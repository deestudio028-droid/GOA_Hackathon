#!/usr/bin/env python3
"""
==============================================================================
Task 3 - Phase 2: Face Identification Module (Detection + Encoding)
HH Goa 2026 Shortlisting Challenge

This module provides a production-grade face detection and face encoding
pipeline built with pretrained deep learning models (MTCNN + InceptionResnetV1
pretrained on VGGFace2).

Key Capabilities:
- Detects all visible human faces in an input image.
- Computes accurate bounding boxes [x1, y1, x2, y2] and confidence scores.
- Extracts and saves normalized face crops into phase2/output/faces/.
- Generates 512-dimensional L2-normalized face embeddings/encodings.
- Operates reliably on CPU (and CUDA GPU if available) on Windows/Linux/macOS.
- Clean programmatic API (`identify_faces()`) for downstream integration.

NO model training required. Pretrained models used exclusively.
NO hardcoded detection or embedding values.
==============================================================================
"""

import os
import sys
import io
import json
import argparse
from typing import List, Dict, Any, Optional, Tuple

# Ensure UTF-8 output encoding for cross-platform terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageOps
import numpy as np
import torch


# ==============================================================================
# Custom Exceptions
# ==============================================================================

class FaceIdentificationError(Exception):
    """Base exception for face identification errors."""
    pass


class ImageNotFoundError(FaceIdentificationError):
    """Raised when the specified image path does not exist."""
    pass


class InvalidImageError(FaceIdentificationError):
    """Raised when the image file is corrupted, empty, or unreadable."""
    pass


class ModelLoadError(FaceIdentificationError):
    """Raised when pretrained face detection/recognition models fail to load."""
    pass


class NoFaceDetectedError(FaceIdentificationError):
    """Raised when no human faces are found in the input image."""
    pass


# ==============================================================================
# Model Manager (Singleton for Fast In-Memory Inference)
# ==============================================================================

class FaceModelManager:
    """Manages lazy-loading and singleton instances of MTCNN and InceptionResnetV1."""
    _instance = None
    _mtcnn = None
    _resnet = None
    _device = None

    @classmethod
    def get_models(cls) -> Tuple[Any, Any, torch.device]:
        if cls._mtcnn is None or cls._resnet is None:
            try:
                from facenet_pytorch import MTCNN, InceptionResnetV1
            except ImportError as e:
                raise ModelLoadError(
                    f"facenet-pytorch is not installed. Please run: pip install facenet-pytorch. ({e})"
                )

            try:
                # Use CPU by default for maximum deterministic compatibility across environments
                # Can leverage CUDA if GPU device is available
                cls._device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
                
                # Multi-face MTCNN detector
                cls._mtcnn = MTCNN(
                    keep_all=True,
                    device=cls._device,
                    selection_method="probability",
                    post_process=False
                )

                # Pretrained InceptionResnetV1 on VGGFace2 dataset (512-dim embeddings)
                cls._resnet = InceptionResnetV1(pretrained="vggface2").eval().to(cls._device)
            except Exception as e:
                raise ModelLoadError(f"Failed to initialize pretrained face models: {str(e)}")

        return cls._mtcnn, cls._resnet, cls._device


# ==============================================================================
# Core Face Identification Pipeline API
# ==============================================================================

def validate_image(image_path: str) -> Image.Image:
    """
    Validates existence and file integrity of the input image.

    Returns:
        PIL.Image.Image: Opened RGB image object.
    """
    if not os.path.exists(image_path):
        raise ImageNotFoundError(f"Image file does not exist at path: '{image_path}'")

    if not os.path.isfile(image_path):
        raise InvalidImageError(f"Specified path is not a valid file: '{image_path}'")

    try:
        with open(image_path, "rb") as f:
            raw = f.read()
    except Exception as e:
        raise InvalidImageError(f"Cannot read image file '{image_path}': {str(e)}")

    if len(raw) == 0:
        raise InvalidImageError(f"Image file is empty (0 bytes): '{image_path}'")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        # Re-open after verify to load pixel buffer
        img = Image.open(io.BytesIO(raw))
        # Handle EXIF orientation if present
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except Exception as e:
        raise InvalidImageError(f"File '{image_path}' is corrupted or an unsupported image format: {str(e)}")


def identify_faces(
    image_path: str,
    output_dir: Optional[str] = None,
    save_crops: bool = True,
    confidence_threshold: float = 0.80
) -> Dict[str, Any]:
    """
    Detects all visible human faces in an image, extracts normalized crops,
    and computes 512-dimensional pretrained face embeddings.

    Args:
        image_path: Path to the local input image file.
        output_dir: Directory where face crops will be saved (default: phase2/output/faces/).
        save_crops: Whether to save cropped face images to disk.
        confidence_threshold: Minimum detection confidence to consider a valid face (default: 0.80).

    Returns:
        Dict containing image path and list of detected faces with bounding boxes,
        confidences, embedding dimensions, and raw 512-dim embedding vectors.
    """
    # 1. Validate image
    img = validate_image(image_path)
    img_w, img_h = img.size

    # 2. Setup output directory
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "faces")
    
    if save_crops:
        os.makedirs(output_dir, exist_ok=True)

    # 3. Load pretrained models
    mtcnn, resnet, device = FaceModelManager.get_models()

    # 4. Perform face detection
    try:
        boxes, probs = mtcnn.detect(img)
    except Exception as e:
        raise FaceIdentificationError(f"Face detection inference failed: {str(e)}")

    faces_result: List[Dict[str, Any]] = []

    if boxes is not None and probs is not None:
        face_idx = 1
        for box, prob in zip(boxes, probs):
            confidence = float(prob) if prob is not None else 0.0
            if confidence < confidence_threshold:
                continue

            # Convert bounding box coordinates to clamped integers
            x1 = max(0, int(round(box[0])))
            y1 = max(0, int(round(box[1])))
            x2 = min(img_w, int(round(box[2])))
            y2 = min(img_h, int(round(box[3])))

            # Check valid crop dimensions
            if x2 <= x1 or y2 <= y1:
                continue

            face_id = f"face_{face_idx:02d}"

            # 5. Extract and save face crop
            crop = img.crop((x1, y1, x2, y2))
            crop_path = None
            if save_crops:
                crop_path = os.path.join(output_dir, f"{face_id}.jpg")
                crop.save(crop_path, "JPEG", quality=95)

            # 6. Generate 512-dimensional face embedding using InceptionResnetV1
            # Resize crop to 160x160 (standard input dimension for Inception-ResNet-v1)
            crop_resized = crop.resize((160, 160), Image.Resampling.BILINEAR)
            crop_array = np.array(crop_resized).astype(np.float32)
            
            # Standard FaceNet fixed normalization: (x - 127.5) / 128.0
            crop_tensor = torch.tensor(crop_array).permute(2, 0, 1).float()
            crop_tensor = (crop_tensor - 127.5) / 128.0
            crop_tensor = crop_tensor.unsqueeze(0).to(device)

            with torch.no_grad():
                raw_embedding = resnet(crop_tensor).squeeze(0)
                # L2 normalize embedding for cosine similarity comparisons
                norm_embedding = torch.nn.functional.normalize(raw_embedding, p=2, dim=0)
                embedding_list = norm_embedding.cpu().numpy().tolist()

            faces_result.append({
                "face_id": face_id,
                "bbox": [x1, y1, x2, y2],
                "confidence": round(confidence, 4),
                "crop_path": crop_path,
                "embedding_dimension": len(embedding_list),
                "embedding": embedding_list
            })

            face_idx += 1

    return {
        "image": image_path,
        "faces_detected": len(faces_result),
        "faces": faces_result
    }


# ==============================================================================
# CLI Formatting & Terminal Display
# ==============================================================================

def display_identification_results(result: Dict[str, Any], show_embeddings: bool = False) -> None:
    """Prints terminal output following the exact required format."""
    print("========================================")
    print("PHASE 2 - FACE IDENTIFICATION")
    print("========================================")
    print()
    print("Input:")
    print(result["image"])
    print()
    print("✓ Image validated")
    print("✓ Face detection completed")
    print()

    faces = result.get("faces", [])
    if not faces:
        print("[NOTICE] No human faces were detected in the input image.")
        print()
    else:
        for f in faces:
            face_label = f["face_id"].replace("_", " ").upper()
            print(face_label)
            print(f"Bounding box: {f['bbox']}")
            print(f"Confidence: {f['confidence']}")
            print(f"Embedding dimension: {f['embedding_dimension']}")
            if show_embeddings:
                print(f"Embedding vector (first 5 elements): {f['embedding'][:5]}...")
            print()

        print("✓ Face encoding completed")
        print()

    print(f"Faces detected: {len(faces)}")
    print()
    print("========================================")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: Face Identification Module (Detection + Pretrained Encoding)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python face_identifier.py --image test_images/single_face.jpg
  python face_identifier.py --image test_images/multiple_faces.jpg
  python face_identifier.py --image test_images/no_face.jpg
  python face_identifier.py --image test_images/single_face.jpg --json
        """
    )
    parser.add_argument(
        "positional_image",
        nargs="?",
        default=None,
        help="Path to the query image (optional if --image is specified)"
    )
    parser.add_argument(
        "--image", "-i",
        dest="image_path",
        default=None,
        help="Path to the input image file (JPEG, PNG, WebP)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Custom directory to save extracted face crops (default: phase2/output/faces/)"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.80,
        help="Confidence threshold for face detection (default: 0.80)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as clean JSON for pipeline integration"
    )
    parser.add_argument(
        "--show-embeddings",
        action="store_true",
        help="Display preview of the embedding vector in terminal output"
    )

    args = parser.parse_args()
    image_path = args.image_path or args.positional_image

    if not image_path:
        default_test = os.path.join(os.path.dirname(__file__), "test_images", "single_face.jpg")
        if os.path.exists(default_test):
            image_path = default_test
        else:
            parser.print_help()
            print("\nError: Please provide an image path via --image or positional argument.")
            sys.exit(1)

    try:
        result = identify_faces(
            image_path=image_path,
            output_dir=args.output_dir,
            save_crops=True,
            confidence_threshold=args.threshold
        )

        if args.json:
            # Create a serializable summary for JSON output
            json_data = {
                "image": result["image"],
                "faces_detected": result["faces_detected"],
                "faces": [
                    {
                        "face_id": f["face_id"],
                        "bbox": f["bbox"],
                        "confidence": f["confidence"],
                        "crop_path": f["crop_path"],
                        "embedding_dimension": f["embedding_dimension"],
                        "embedding": f["embedding"] if args.show_embeddings else f"[{len(f['embedding'])} float values]"
                    }
                    for f in result["faces"]
                ]
            }
            print(json.dumps(json_data, indent=2))
        else:
            display_identification_results(result, show_embeddings=args.show_embeddings)

    except ImageNotFoundError as e:
        print(f"\n[ERROR: IMAGE NOT FOUND] {e}", file=sys.stderr)
        sys.exit(2)
    except InvalidImageError as e:
        print(f"\n[ERROR: INVALID IMAGE] {e}", file=sys.stderr)
        sys.exit(2)
    except ModelLoadError as e:
        print(f"\n[ERROR: MODEL LOADING FAILED] {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
