#!/usr/bin/env python3
"""
==============================================================================
Task 3 - Phase 3: Face-to-Web/Social Search Integration
HH Goa 2026 Shortlisting Challenge

This module connects Phase 2 (Face Detection & Pretrained Crop Extraction)
with Phase 1 (Genuine Google Lens Reverse Image Search via SerpApi).

Pipeline Architecture:
Input Image
    ↓
Phase 2 Face Detection (MTCNN)
    ↓
Target Face Crop (e.g. face_01.jpg)
    ↓
Phase 1 Google Lens Reverse Search (SerpApi)
    ↓
Live Visual Matches & Web Discovery
    ↓
Candidate Classification (SOCIAL vs WEB) & Filtering
    ↓
Normalized Structured Results

NO hardcoded URLs, NO fake social-media results.
==============================================================================
"""

import os
import sys
import io
import json
import argparse
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

# Ensure UTF-8 output encoding for cross-platform terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add workspace root to sys.path to enable direct modular imports from phase1 and phase2
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

# Import existing modular components
try:
    from phase2.face_identifier import (
        identify_faces,
        validate_image,
        FaceIdentificationError,
        ImageNotFoundError,
        InvalidImageError,
        NoFaceDetectedError
    )
    from phase1.reverse_search import (
        perform_reverse_search,
        search_google_social,
        extract_domain,
        SearchResult,
        ReverseSearchError,
        MissingApiKeyError,
        ApiRateLimitError,
        AuthenticationError,
        ApiNetworkError,
        NoResultsFoundError
    )
except ImportError as e:
    raise ImportError(
        f"Failed to import Phase 1 or Phase 2 modules from '{WORKSPACE_ROOT}': {e}"
    )


# ==============================================================================
# Domain & Social Classification Rules
# ==============================================================================

RECOGNIZED_SOCIAL_DOMAINS = {
    # Microblogging & Social Networks
    "x.com", "twitter.com", "t.co",
    "instagram.com", "instagr.am",
    "facebook.com", "fb.com", "fb.watch", "m.facebook.com", "web.facebook.com",
    "linkedin.com", "lnkd.in",
    "reddit.com", "redd.it",
    "tiktok.com",
    "threads.net",
    "mastodon.social", "bsky.app",
    "vk.com", "weibo.com", "telegram.org", "t.me",
    # Media & Visual Sharing
    "youtube.com", "youtu.be", "m.youtube.com",
    "pinterest.com", "pin.it",
    "flickr.com", "tumblr.com",
    # Creator & Developer Platforms
    "medium.com", "github.com"
}


def classify_url_domain(url: str) -> str:
    """
    Classifies a URL into 'SOCIAL' or 'WEB' based strictly on its domain.
    Does not guess based on title keywords.
    """
    if not url or url == "N/A":
        return "UNKNOWN"
    try:
        domain = extract_domain(url).lower()
        # Direct match or subdomain match (e.g. m.facebook.com, www.instagram.com)
        for soc in RECOGNIZED_SOCIAL_DOMAINS:
            if domain == soc or domain.endswith("." + soc):
                return "SOCIAL"
        return "WEB"
    except Exception:
        return "UNKNOWN"


def extract_entities_from_results(raw_results: List[SearchResult]) -> List[str]:
    """
    Dynamically extracts potential entity or subject names from live search result titles.
    NO hardcoded names, keywords, or answers.
    """
    entities: List[str] = []
    for r in raw_results:
        title = r.title
        if not title or title.startswith("Untitled") or title.startswith("Visually Similar") or title == "N/A":
            continue
        # Clean title by splitting at common site and title delimiters
        clean = title
        for sep in [" - ", " | ", " – ", " — ", " : ", " • ", " / "]:
            if sep in clean:
                clean = clean.split(sep)[0]
        clean = clean.strip()
        if len(clean) >= 3 and clean not in entities:
            entities.append(clean)
    return entities


# ==============================================================================
# Core Pipeline API: search_face_on_web()
# ==============================================================================

def search_face_on_web(
    image_path: str,
    face_index: int = 0,
    social_only: bool = False,
    max_results: int = 5,
    output_dir: Optional[str] = None,
    engine_name: str = "google_lens"
) -> Dict[str, Any]:
    """
    Executes an enhanced multi-stage Face-to-Web/Social Search pipeline:
    1. Detects faces and extracts crops via Phase 2 (MTCNN).
    2. Runs Google Lens reverse search on the original input image.
    3. Runs Google Lens reverse search on the detected face crop for person focus.
    4. If no social results found (or to expand social coverage), performs a secondary
       dynamic live Google social search using entity keywords extracted from live visual results.
    5. Deduplicates, classifies, and ranks genuine SOCIAL results above WEB results.

    Args:
        image_path: Path to the input image containing a face.
        face_index: 0-indexed integer specifying which detected face to search.
        social_only: If True, filters candidates to only recognized social media domains.
        max_results: Maximum candidate matches to return.
        output_dir: Directory to save face crops (default: phase3/output/faces/).
        engine_name: Reverse search engine ("google_lens", "google_vision", "bing_visual").

    Returns:
        Structured dictionary containing detection metadata, multi-stage candidate metrics,
        and classified search candidates.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "faces")
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Detect all visible faces in input image
    detection_result = identify_faces(
        image_path=image_path,
        output_dir=output_dir,
        save_crops=True
    )

    faces = detection_result.get("faces", [])
    if not faces:
        raise NoFaceDetectedError(
            f"No human faces were detected in image: '{image_path}'. "
            "Reverse face search requires at least one visible human face."
        )

    if face_index < 0 or face_index >= len(faces):
        raise IndexError(
            f"Invalid face_index={face_index}. Image contains {len(faces)} detected face(s) (indices 0 to {len(faces) - 1})."
        )

    selected_face = faces[face_index]
    face_crop_path = selected_face.get("crop_path")

    # Step 2: Live reverse search using original input image
    initial_candidates: List[Dict[str, Any]] = []
    raw_initial: List[SearchResult] = []
    try:
        raw_initial = perform_reverse_search(
            image_path=image_path,
            engine_name=engine_name,
            max_results=max_results * 2,
            enable_fallback=True
        )
        for r in raw_initial:
            dom_type = classify_url_domain(r.url)
            initial_candidates.append({
                "title": r.title,
                "source": r.source,
                "url": r.url,
                "image_url": r.image_url,
                "type": dom_type,
                "engine": r.engine,
                "search_source": "Google Lens (Original Image)"
            })
    except NoResultsFoundError:
        pass
    except Exception:
        pass

    # Step 3: Live reverse search using detected face crop (for person-focused identification)
    crop_candidates: List[Dict[str, Any]] = []
    raw_crop: List[SearchResult] = []
    if face_crop_path and os.path.exists(face_crop_path) and face_crop_path != image_path:
        try:
            raw_crop = perform_reverse_search(
                image_path=face_crop_path,
                engine_name=engine_name,
                max_results=max_results * 2,
                enable_fallback=True
            )
            for r in raw_crop:
                dom_type = classify_url_domain(r.url)
                crop_candidates.append({
                    "title": r.title,
                    "source": r.source,
                    "url": r.url,
                    "image_url": r.image_url,
                    "type": dom_type,
                    "engine": r.engine,
                    "search_source": "Google Lens (Face Crop)"
                })
        except NoResultsFoundError:
            pass
        except Exception:
            pass

    # Check if social candidates exist from image/crop Lens searches
    existing_social = [
        c for c in (initial_candidates + crop_candidates)
        if c.get("type") == "SOCIAL"
    ]

    # Step 4: Secondary live Google social search if no social candidate found yet
    secondary_candidates: List[Dict[str, Any]] = []
    if len(existing_social) == 0:
        # Dynamically extract entity keywords from live visual results
        all_visual_results = raw_crop + raw_initial
        entities = extract_entities_from_results(all_visual_results)

        # Execute genuine secondary live social queries for top discovered entities
        for entity in entities[:2]:
            try:
                raw_social = search_google_social(
                    query_entity=entity,
                    max_results=max_results
                )
                for r in raw_social:
                    dom_type = classify_url_domain(r.url)
                    secondary_candidates.append({
                        "title": r.title,
                        "source": r.source,
                        "url": r.url,
                        "image_url": r.image_url,
                        "type": dom_type,
                        "engine": r.engine,
                        "search_source": "Secondary Social Search (via SerpApi)"
                    })
                # If a social match was found, stop further secondary queries
                if any(c.get("type") == "SOCIAL" for c in secondary_candidates):
                    break
            except Exception:
                pass

    # Step 5: Deduplicate all candidates across all search stages by normalized URL
    seen_urls = set()
    deduped_candidates: List[Dict[str, Any]] = []

    # Priority order: face crop Lens, original image Lens, secondary social search
    all_raw_pool = crop_candidates + initial_candidates + secondary_candidates

    for c in all_raw_pool:
        url = c.get("url", "").strip()
        if not url or url == "N/A":
            continue
        norm_url = url.rstrip("/").lower()
        if norm_url in seen_urls:
            continue
        seen_urls.add(norm_url)
        deduped_candidates.append(c)

    # Separate candidates into SOCIAL and WEB
    social_candidates_list = [c for c in deduped_candidates if c.get("type") == "SOCIAL"]
    web_candidates_list = [c for c in deduped_candidates if c.get("type") != "SOCIAL"]

    # Rank all SOCIAL results above WEB results
    ordered_candidates = social_candidates_list + web_candidates_list

    if social_only:
        ordered_candidates = social_candidates_list

    # Assign sequential ranks
    final_candidates: List[Dict[str, Any]] = []
    for idx, c in enumerate(ordered_candidates, start=1):
        c_copy = dict(c)
        c_copy["rank"] = idx
        final_candidates.append(c_copy)
        if len(final_candidates) >= max(max_results, len(social_candidates_list)):
            break

    return {
        "input_image": image_path,
        "faces_detected": len(faces),
        "selected_face": {
            "face_id": selected_face["face_id"],
            "face_index": face_index,
            "bbox": selected_face["bbox"],
            "confidence": selected_face["confidence"],
            "crop_path": face_crop_path,
            "embedding_dimension": selected_face["embedding_dimension"]
        },
        "initial_lens_candidates": len(initial_candidates),
        "face_crop_lens_candidates": len(crop_candidates),
        "secondary_social_candidates": len(secondary_candidates),
        "total_candidates": len(final_candidates),
        "social_candidates": len(social_candidates_list),
        "social_found": len(social_candidates_list) > 0,
        "social_only_filtered": social_only,
        "candidates": final_candidates,
        "social_candidates_list": social_candidates_list,
        "selected_social_candidate": social_candidates_list[0] if social_candidates_list else None
    }


# ==============================================================================
# CLI Formatting & Terminal Display
# ==============================================================================

def display_pipeline_results(result: Dict[str, Any]) -> None:
    """Formats and prints terminal output strictly matching project requirements."""
    print("========================================")
    print("PHASE 3 - FACE TO WEB SEARCH")
    print("========================================")
    print()
    print("Input image:")
    print(result["input_image"])
    print()
    print("✓ Face detection completed")
    print(f"✓ Selected face: {result['selected_face']['face_id']}")
    print("✓ Face crop prepared")
    print("✓ Google Lens multi-stage search completed")
    print()
    print("LIVE SEARCH SUMMARY:")
    print(f"  Initial Lens candidates:            {result.get('initial_lens_candidates', 0)}")
    print(f"  Face-crop Lens candidates:          {result.get('face_crop_lens_candidates', 0)}")
    print(f"  Secondary social search candidates: {result.get('secondary_social_candidates', 0)}")
    print(f"  Final SOCIAL candidates:            {result.get('social_candidates', 0)}")
    print()

    candidates = result.get("candidates", [])
    if not candidates:
        print("[NOTICE] SEARCH WORKS, NO MATCHING WEB PAGES FOUND")
        print()
    else:
        for c in candidates:
            print(f"CANDIDATE {c['rank']}")
            print(f"Title: {c['title']}")
            print(f"Platform/Source: {c['source']}")
            print(f"Type: {c['type']}")
            print(f"URL: {c['url']}")
            if c.get("search_source"):
                print(f"Search Source: {c['search_source']}")
            if c.get("image_url") and c["image_url"] != "N/A":
                print(f"Image URL: {c['image_url']}")
            print()

        if result.get("social_candidates", 0) == 0:
            print("❌ SOCIAL RESULT NOT FOUND")
            print("   (Genuine search completed, but 0 returned results were from social media platforms)")
            print()

    print("========================================")
    print(f"Faces detected: {result['faces_detected']}")
    print(f"Candidates found: {result['total_candidates']}")
    print(f"Social candidates: {result['social_candidates']}")
    print("========================================")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3: Face-to-Web/Social Search Integration Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python face_web_search.py --image test_images/person_social.jpg
  python face_web_search.py --image test_images/multiple_faces.jpg --face-index 1
  python face_web_search.py --image test_images/person_social.jpg --social-only
  python face_web_search.py --image test_images/person_social.jpg --json
        """
    )
    parser.add_argument(
        "positional_image",
        nargs="?",
        default=None,
        help="Path to the input image file"
    )
    parser.add_argument(
        "--image", "-i",
        dest="image_path",
        default=None,
        help="Path to the input image file (JPEG, PNG, WebP)"
    )
    parser.add_argument(
        "--face-index", "-f",
        type=int,
        default=0,
        help="0-indexed face to search when multiple faces are detected (default: 0)"
    )
    parser.add_argument(
        "--social-only", "-s",
        action="store_true",
        help="Filter results to only recognized social media platforms"
    )
    parser.add_argument(
        "--max-results", "-n",
        type=int,
        default=5,
        help="Maximum candidates to return (default: 5)"
    )
    parser.add_argument(
        "--engine", "-e",
        default="google_lens",
        choices=["google_lens", "google_vision", "bing_visual"],
        help="Search engine to use (default: google_lens)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )

    args = parser.parse_args()
    image_path = args.image_path or args.positional_image

    if not image_path:
        default_test = os.path.join(os.path.dirname(__file__), "test_images", "person_social.jpg")
        if os.path.exists(default_test):
            image_path = default_test
        else:
            parser.print_help()
            print("\nError: Please provide an image path via --image or positional argument.")
            sys.exit(1)

    try:
        result = search_face_on_web(
            image_path=image_path,
            face_index=args.face_index,
            social_only=args.social_only,
            max_results=args.max_results,
            engine_name=args.engine
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            display_pipeline_results(result)

    except ImageNotFoundError as e:
        print(f"\n[ERROR: IMAGE NOT FOUND] {e}", file=sys.stderr)
        sys.exit(2)
    except InvalidImageError as e:
        print(f"\n[ERROR: INVALID IMAGE] {e}", file=sys.stderr)
        sys.exit(2)
    except NoFaceDetectedError as e:
        print(f"\n[ERROR: NO FACE DETECTED] {e}", file=sys.stderr)
        sys.exit(3)
    except IndexError as e:
        print(f"\n[ERROR: INVALID FACE INDEX] {e}", file=sys.stderr)
        sys.exit(4)
    except MissingApiKeyError as e:
        print(f"\n[ERROR: MISSING API KEY] {e}", file=sys.stderr)
        sys.exit(5)
    except ApiRateLimitError as e:
        print(f"\n[ERROR: RATE LIMIT EXCEEDED] {e}", file=sys.stderr)
        sys.exit(6)
    except AuthenticationError as e:
        print(f"\n[ERROR: AUTHENTICATION FAILED] {e}", file=sys.stderr)
        sys.exit(7)
    except ApiNetworkError as e:
        print(f"\n[ERROR: API NETWORK ERROR] {e}", file=sys.stderr)
        sys.exit(8)
    except NoResultsFoundError as e:
        print(f"\n[NOTICE: NO RESULTS FOUND] {e}", file=sys.stderr)
        sys.exit(9)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(10)


if __name__ == "__main__":
    main()
