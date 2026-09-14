import os
import sys
import json
import time

# ---------------------------------------------------------------------------
# UTF-8 terminal output
# ---------------------------------------------------------------------------

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Workspace setup
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

from phase2.face_identifier import identify_faces

from phase3.face_web_search import search_face_on_web

from phase4.blockchain_anchor import (
    create_canonical_representation,
    generate_sha256_fingerprint,
    BlockchainAnchorClient
)

from phase5.verify_integrity import (
    verify_candidate_integrity
)


# ===========================================================================
# CONFIGURATION
# ===========================================================================

INPUT_IMAGES = [
    os.path.join(WORKSPACE_ROOT, "test1.jpeg"),
    os.path.join(WORKSPACE_ROOT, "test2.jpeg"),
    os.path.join(WORKSPACE_ROOT, "test3.jpeg"),
    
]

MAX_SEARCH_RESULTS = 5


# ===========================================================================
# HELPERS
# ===========================================================================

def print_separator(char="=", length=70):
    print(char * length)


def create_tampered_candidate(candidate):
    """
    Modify exactly one character in the URL so SHA-256 changes.
    """

    tampered = dict(candidate)

    original_url = candidate.get("url", "")

    if not original_url:
        tampered["url"] = "https://tampered.example/test"
        return tampered

    # Change one character near the end while preserving the URL shape.
    last_char = original_url[-1]

    if last_char.isdigit():
        replacement = "9" if last_char != "9" else "8"
    else:
        replacement = "x" if last_char != "x" else "y"

    tampered["url"] = original_url[:-1] + replacement

    return tampered


def run_single_image(image_path, image_number, blockchain_client):
    """
    Run complete pipeline for one image.
    """

    print_separator()
    print(f"IMAGE {image_number} / {len(INPUT_IMAGES)}")
    print_separator()

    print(f"[STAGE 1] INPUT IMAGE")
    print(f"Path: {image_path}")

    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return {
            "image": os.path.basename(image_path),
            "status": "IMAGE_NOT_FOUND",
            "social_found": False,
            "selected_platform": "N/A",
            "selected_url": "N/A"
        }

    print("✓ Image file located and readable.")
    print()

    # -----------------------------------------------------------------------
    # STAGE 2 - FACE DETECTION + EMBEDDING
    # -----------------------------------------------------------------------

    print("[STAGE 2] FACE DETECTION & 512-D ENCODING")
    print("-" * 70)

    detection = identify_faces(image_path)

    faces = detection.get("faces", [])

    print(f"✓ Faces detected: {len(faces)}")

    if len(faces) == 0:
        print("❌ No face detected.")
        return {
            "image": os.path.basename(image_path),
            "status": "NO_FACE",
            "faces": 0,
            "candidates": 0,
            "social_candidates": 0,
            "social_found": False,
            "selected_platform": "N/A",
            "selected_url": "N/A"
        }

    face0 = faces[0]

    print(f"  Face ID:              {face0['face_id']}")
    print(f"  Bounding Box:         {face0['bbox']}")
    print(f"  Confidence:           {face0['confidence']}")
    print(f"  Embedding Dimension:  {face0['embedding_dimension']}-D")
    print(f"  Face Crop:            {face0['crop_path']}")
    print()

    # -----------------------------------------------------------------------
    # STAGE 3 - MULTI-STAGE LIVE WEB & SOCIAL REVERSE SEARCH
    # -----------------------------------------------------------------------

    print("[STAGE 3] MULTI-STAGE LIVE WEB & SOCIAL REVERSE SEARCH")
    print("-" * 70)

    search_res = search_face_on_web(
        image_path=image_path,
        face_index=0,
        social_only=False,
        max_results=MAX_SEARCH_RESULTS
    )

    candidates = search_res.get("candidates", [])
    social_candidates = search_res.get("social_candidates_list", [])
    if not social_candidates:
        social_candidates = [c for c in candidates if str(c.get("type", "")).upper() == "SOCIAL"]

    initial_lens_count = search_res.get("initial_lens_candidates", 0)
    face_crop_lens_count = search_res.get("face_crop_lens_candidates", 0)
    secondary_social_count = search_res.get("secondary_social_candidates", 0)
    final_social_count = len(social_candidates)

    print("LIVE SEARCH SUMMARY:")
    print(f"  Initial Lens candidates:            {initial_lens_count}")
    print(f"  Face-crop Lens candidates:          {face_crop_lens_count}")
    print(f"  Secondary social search candidates: {secondary_social_count}")
    print(f"  Final SOCIAL candidates:            {final_social_count}")
    print()

    if len(candidates) == 0:
        print("❌ Zero candidates returned from live searches.")
        return {
            "image": os.path.basename(image_path),
            "status": "NO_SEARCH_RESULTS",
            "faces": len(faces),
            "candidates": 0,
            "social_candidates": 0,
            "social_found": False,
            "top_candidate": None
        }

    # Print all candidates for demo visibility
    print("DISCOVERED CANDIDATES:")
    print()

    for index, candidate in enumerate(candidates, start=1):
        print(f"  [{index}] {candidate.get('title', 'Unknown')}")
        print(f"      Platform:      {candidate.get('source', 'Unknown')}")
        print(f"      Type:          {candidate.get('type', 'Unknown')}")
        print(f"      URL:           {candidate.get('url', 'Unknown')}")
        if candidate.get("search_source"):
            print(f"      Search Source: {candidate.get('search_source')}")
        print()

    # Require genuine SOCIAL candidate for blockchain anchoring
    if not social_candidates:
        print("❌ SOCIAL RESULT NOT FOUND")
        print("  All genuine live search attempts exhausted without finding a supported social media URL.")
        print("  Attempts performed:")
        print("    1. Google Lens reverse image search on original input image")
        print("    2. Google Lens reverse image search on detected face crop")
        print("    3. Secondary live Google/SerpApi social media search on discovered entities")
        print("  Do not anchor fake or non-social placeholder URLs.")
        print()
        return {
            "image": os.path.basename(image_path),
            "status": "SOCIAL_NOT_FOUND",
            "faces": len(faces),
            "candidates": len(candidates),
            "social_candidates": 0,
            "social_found": False,
            "top_candidate": None
        }

    # Top candidate: genuine SOCIAL result
    top_candidate = social_candidates[0]
    selection_reason = "Genuine SOCIAL candidate selected via multi-stage search"
    search_source = top_candidate.get("search_source", top_candidate.get("engine", "Google Lens / SerpApi"))

    print("FINAL SOCIAL MATCH:")
    print(f"  Title:            {top_candidate['title']}")
    print(f"  Platform:         {top_candidate['source']}")
    print(f"  Type:             {top_candidate['type']}")
    print(f"  URL:              {top_candidate['url']}")
    print(f"  Search source:    {search_source}")
    print(f"  Selection reason: {selection_reason}")
    print()

    # -----------------------------------------------------------------------
    # STAGE 4 - CANONICAL JSON + SHA-256
    # -----------------------------------------------------------------------

    print("[STAGE 4] CANONICAL JSON & SHA-256 FINGERPRINT")
    print("-" * 70)

    canonical_json = create_canonical_representation(top_candidate)

    sha256_hash = generate_sha256_fingerprint(canonical_json)

    print("✓ Canonical representation generated.")
    print(f"✓ Canonical JSON: {canonical_json}")
    print()
    print(f"✓ SHA-256:")
    print(f"  {sha256_hash}")
    print()

    # -----------------------------------------------------------------------
    # STAGE 5 - POLYGON AMOY
    # -----------------------------------------------------------------------

    print("[STAGE 5] POLYGON AMOY BLOCKCHAIN ANCHOR")
    print("-" * 70)

    try:
        blockchain_client.validate_connection()

        anchor_rec = blockchain_client.anchor_fingerprint(sha256_hash)

        print(f"✓ Network:          {anchor_rec['network']}")
        print(f"✓ Chain ID:         {anchor_rec['chain_id']}")
        print(f"✓ Contract:         {anchor_rec['contract_address']}")
        print(f"✓ Transaction Hash: {anchor_rec['transaction_hash']}")
        print(f"✓ Confirmed Block:  #{anchor_rec['block_number']}")
        print(f"✓ Anchored By:      {anchor_rec['anchored_by']}")
        print(f"✓ Timestamp:        {anchor_rec['anchored_at_iso']}")
        print(f"✓ Status:            {anchor_rec['status']}")

        assert anchor_rec["verification"]["matches_local_hash"] is True

        print("✓ Local hash matches on-chain hash.")
        print()

    except Exception as exc:

        print(f"❌ Blockchain anchoring failed: {exc}")

        return {
            "image": os.path.basename(image_path),
            "status": "BLOCKCHAIN_ERROR",
            "faces": len(faces),
            "candidates": len(candidates),
            "social_candidates": len(social_candidates),
            "social_found": True,
            "candidate": top_candidate,
            "selected_platform": top_candidate.get("source", "Unknown"),
            "selected_url": top_candidate.get("url", "N/A"),
            "sha256": sha256_hash,
            "error": str(exc)
        }

    # -----------------------------------------------------------------------
    # STAGE 6 - INDEPENDENT VERIFICATION
    # -----------------------------------------------------------------------

    print("[STAGE 6] INDEPENDENT VERIFICATION & TAMPER DETECTION")
    print("-" * 70)

    # =======================================================================
    # CHECK 6A - ORIGINAL
    # =======================================================================

    print()
    print("CHECK 6A: ORIGINAL CANDIDATE")

    verif_orig = verify_candidate_integrity(top_candidate)

    print(f"  Calculated Hash: {verif_orig['current_hash']}")

    print(
        "  On-Chain Status: "
        f"Anchored={verif_orig['blockchain'].get('is_anchored', False)}"
    )

    print(
        f"  Block Number:    "
        f"#{verif_orig['blockchain'].get('block_number')}"
    )

    print(f"  Verdict:         {verif_orig['status']}")

    if verif_orig["status"] == "VERIFIED":
        print("  --> ✅ VERIFIED")
    else:
        print("  --> ❌ VERIFICATION FAILED")

    print()

    # =======================================================================
    # CHECK 6B - TAMPERED
    # =======================================================================

    print("CHECK 6B: TAMPER DETECTION")

    tampered_candidate = create_tampered_candidate(top_candidate)

    print(f"  Original URL:")
    print(f"    {top_candidate['url']}")

    print()
    print(f"  Tampered URL:")
    print(f"    {tampered_candidate['url']}")

    verif_tampered = verify_candidate_integrity(
        tampered_candidate,
        expected_hash=sha256_hash
    )

    print()
    print(f"  Tampered Hash: {verif_tampered['current_hash']}")
    print(f"  Expected Hash: {verif_tampered['expected_hash']}")
    print(f"  Hashes Match:  {verif_tampered['hashes_match']}")
    print(f"  Verdict:       {verif_tampered['status']}")

    if verif_tampered["status"] == "TAMPERED":
        print("  --> ❌ TAMPERED — CHANGE DETECTED")
    else:
        print("  --> ⚠️ Tamper detection result unexpected")

    print()

    # =======================================================================
    # CHECK 6C - UNANCHORED
    # =======================================================================

    print("CHECK 6C: UNANCHORED DATA")

    unanchored_candidate = {
        "title": "Random Unanchored Web Discovery",
        "source": "example.org",
        "url": "https://example.org/random_post_99999",
        "type": "WEB",
        "engine": "Google Lens"
    }

    verif_unanchored = verify_candidate_integrity(
        unanchored_candidate
    )

    print(
        f"  Unanchored Hash: "
        f"{verif_unanchored['current_hash']}"
    )

    print(
        "  On-Chain Status: "
        f"Anchored={verif_unanchored['blockchain'].get('is_anchored', False)}"
    )

    print(
        f"  Verdict: "
        f"{verif_unanchored['status']}"
    )

    if verif_unanchored["status"] == "NOT_ANCHORED":
        print("  --> ⚠️ NOT_ANCHORED")
    else:
        print("  --> Unexpected result")

    print()

    # -----------------------------------------------------------------------
    # IMAGE RESULT
    # -----------------------------------------------------------------------

    image_success = (
        verif_orig["status"] == "VERIFIED"
        and verif_tampered["status"] == "TAMPERED"
        and verif_unanchored["status"] == "NOT_ANCHORED"
    )

    if image_success:
        print("✅ IMAGE PIPELINE PASSED")
    else:
        print("❌ IMAGE PIPELINE FAILED")

    print()

    return {
        "image": os.path.basename(image_path),
        "status": "PASSED" if image_success else "FAILED",
        "faces": len(faces),
        "candidates": len(candidates),
        "social_candidates": len(social_candidates),
        "social_found": True,
        "top_candidate": top_candidate,
        "selected_platform": top_candidate.get("source", "Unknown"),
        "selected_url": top_candidate.get("url", "N/A"),
        "sha256": sha256_hash,
        "transaction_hash": anchor_rec["transaction_hash"],
        "block_number": anchor_rec["block_number"],
        "original_verdict": verif_orig["status"],
        "tampered_verdict": verif_tampered["status"],
        "unanchored_verdict": verif_unanchored["status"]
    }


# ===========================================================================
# MAIN PIPELINE
# ===========================================================================

def run_e2e_pipeline():

    print()
    print_separator("=")

    print(f"TASK #3: {len(INPUT_IMAGES)}-IMAGE END-TO-END PIPELINE")
    print("HH GOA 2026 SHORTLISTING CHALLENGE")

    print_separator("=")

    print()
    print("Pipeline:")
    print("  Image")
    print("    ↓")
    print("  MTCNN Face Detection")
    print("    ↓")
    print("  512-D Face Embedding")
    print("    ↓")
    print("  Multi-Stage Live Google Lens & Social Search")
    print("    ↓")
    print("  Genuine Social Media Discovery")
    print("    ↓")
    print("  Canonical JSON")
    print("    ↓")
    print("  SHA-256 Fingerprint")
    print("    ↓")
    print("  Polygon Amoy")
    print("    ↓")
    print("  Independent Verification")
    print("    ↓")
    print("  VERIFIED / TAMPERED / NOT_ANCHORED")
    print()

    print(f"Images to process: {len(INPUT_IMAGES)}")

    for index, image in enumerate(INPUT_IMAGES, start=1):
        print(f"  {index}. {image}")

    print()

    # -----------------------------------------------------------------------
    # Create ONE blockchain client and reuse it
    # -----------------------------------------------------------------------

    print("[INITIALIZATION] Connecting to Polygon Amoy...")
    print()

    try:
        blockchain_client = BlockchainAnchorClient()
        blockchain_client.validate_connection()

        print("✓ Polygon Amoy connection successful.")
        print()

    except Exception as exc:

        print("❌ Could not connect to Polygon Amoy.")
        print(f"Error: {exc}")
        return

    # -----------------------------------------------------------------------
    # Run all images
    # -----------------------------------------------------------------------

    results = []

    for image_number, image_path in enumerate(INPUT_IMAGES, start=1):

        try:

            result = run_single_image(
                image_path=image_path,
                image_number=image_number,
                blockchain_client=blockchain_client
            )

            results.append(result)

        except Exception as exc:

            print()
            print(f"❌ Unexpected error while processing Image {image_number}")
            print(f"Error: {exc}")
            print()

            results.append({
                "image": image_path,
                "status": "ERROR",
                "social_found": False,
                "selected_platform": "N/A",
                "selected_url": "N/A",
                "error": str(exc)
            })

        # Small delay between live searches
        if image_number < len(INPUT_IMAGES):
            print("Waiting briefly before next live search...")
            time.sleep(2)
            print()

    # -----------------------------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------------------------

    print()
    print_separator("=")
    print(f"FINAL {len(INPUT_IMAGES)}-IMAGE PIPELINE SUMMARY")
    print_separator("=")

    passed = 0

    for index, result in enumerate(results, start=1):

        image_basename = os.path.basename(result.get("image", f"Image {index}"))
        print()
        print(f"IMAGE {index}: {image_basename}")
        social_status = "FOUND" if result.get("social_found") else "NOT FOUND"
        print(f"  Social Result:     {social_status}")
        print(f"  Selected Platform: {result.get('selected_platform', 'N/A')}")
        print(f"  Selected URL:      {result.get('selected_url', 'N/A')}")
        print(f"  Status:            {result.get('status', 'UNKNOWN')}")

        if result.get("status") == "PASSED":

            passed += 1

            print(
                f"  Faces:             "
                f"{result.get('faces', 'N/A')}"
            )

            print(
                f"  Search Candidates: "
                f"{result.get('candidates', 'N/A')}"
            )

            print(
                f"  Social Candidates: "
                f"{result.get('social_candidates', 'N/A')}"
            )

            print(
                f"  SHA-256:           "
                f"{result.get('sha256', 'N/A')}"
            )

            print(
                f"  Transaction:       "
                f"{result.get('transaction_hash', 'N/A')}"
            )

            print(
                f"  Block:             "
                f"#{result.get('block_number', 'N/A')}"
            )

            print(
                f"  Original:          "
                f"{result.get('original_verdict', 'N/A')}"
            )

            print(
                f"  Tampered:          "
                f"{result.get('tampered_verdict', 'N/A')}"
            )

            print(
                f"  Unanchored:        "
                f"{result.get('unanchored_verdict', 'N/A')}"
            )

        else:

            if result.get("error"):
                print(f"  Error:             {result['error']}")

    print()
    print_separator("=")

    print(
        f"RESULT: {passed}/{len(INPUT_IMAGES)} IMAGE PIPELINES PASSED"
    )

    if passed == len(INPUT_IMAGES):

        print()
        print(f"🎉 ALL {len(INPUT_IMAGES)} IMAGES PASSED!")
        print()
        print("✓ Real face detection")
        print("✓ Real 512-D face encoding")
        print("✓ Real multi-stage Google Lens reverse search")
        print("✓ Real genuine social discovery")
        print("✓ SHA-256 fingerprinting")
        print("✓ Polygon Amoy blockchain anchoring")
        print("✓ Independent verification")
        print("✓ Tamper detection")
        print("✓ Unanchored detection")

    else:

        print()
        print("⚠️ Some images did not complete successfully.")
        print("Check the individual image output above.")

    print()
    print_separator("=")
    print("END-TO-END PIPELINE COMPLETED")
    print_separator("=")
    print()


# ===========================================================================
# ENTRY POINT
# ===========================================================================

if __name__ == "__main__":
    run_e2e_pipeline()