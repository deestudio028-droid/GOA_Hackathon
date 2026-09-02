#!/usr/bin/env python3
"""
==============================================================================
Task #3: Complete End-to-End Pipeline Integration Test (Phases 1–5)
HH Goa 2026 Shortlisting Challenge

End-to-End Data Flow:
[Input Image]
      │
      ▼ (Phase 2: MTCNN)
[Face Detection & 512-D Embedding]
      │
      ▼ (Face Crop)
[Phase 3: SerpApi Google Lens Reverse Search]
      │
      ▼ (Live Web & Social Candidates)
[Phase 4: Canonical JSON & SHA-256 Fingerprint]
      │
      ▼ (Polygon Amoy Testnet Check)
[Phase 5: On-Chain Integrity & Tamper Detection]
      │
      ▼
[VERIFIED / TAMPERED / NOT_ANCHORED Verdicts]

NO MOCKS. Real neural networks, live search, and active Polygon Amoy RPC.
==============================================================================
"""

import os
import sys
import io
import json
import time

# Ensure UTF-8 output encoding for cross-platform terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add workspace to path
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from dotenv import load_dotenv
load_dotenv()

from phase2.face_identifier import identify_faces
from phase3.face_web_search import search_face_on_web
from phase4.blockchain_anchor import (
    create_canonical_representation,
    generate_sha256_fingerprint,
    BlockchainAnchorClient
)
from phase5.verify_integrity import (
    BlockchainVerifier,
    verify_candidate_integrity
)


def run_e2e_pipeline():
    print("=" * 60)
    print("TASK #3: END-TO-END PIPELINE AUDIT & INTEGRATION TEST")
    print("=" * 60)
    print()

    # Step 1: Input Image
    input_image = os.path.join(WORKSPACE_ROOT, "phase3", "test_images", "musician_social.jpg")
    print(f"[STAGE 1] Input Image: {input_image}")
    assert os.path.exists(input_image), f"Input image missing: {input_image}"
    print("✓ Image file located and readable.")
    print()

    # Step 2: Phase 2 Face Detection & 512-D Encoding
    print("[STAGE 2] Running Phase 2 Face Detection & Encoding (MTCNN + InceptionResnetV1)...")
    detection = identify_faces(input_image)
    faces = detection.get("faces", [])
    print(f"✓ Faces detected: {len(faces)}")
    assert len(faces) > 0, "No faces detected in input image!"
    
    face0 = faces[0]
    print(f"  - Face ID:             {face0['face_id']}")
    print(f"  - Bounding Box:        {face0['bbox']}")
    print(f"  - Confidence:          {face0['confidence']}")
    print(f"  - Embedding Dimension: {face0['embedding_dimension']}-D")
    print(f"  - Face Crop Saved:     {face0['crop_path']}")
    print()

    # Step 3: Phase 3 Web & Social Reverse Search
    print("[STAGE 3] Running Phase 3 Reverse Search (SerpApi Google Lens)...")
    search_res = search_face_on_web(
        image_path=input_image,
        face_index=0,
        social_only=False,
        max_results=5
    )
    candidates = search_res.get("candidates", [])
    print(f"✓ Candidates retrieved: {len(candidates)}")
    print(f"✓ Social candidates:   {search_res.get('social_candidates', 0)}")
    assert len(candidates) > 0, "Zero candidates returned from Google Lens!"
    
    top_cand = candidates[0]
    print(f"  - Top Candidate Title:    {top_cand['title']}")
    print(f"  - Top Candidate Platform: {top_cand['source']}")
    print(f"  - Top Candidate Type:     {top_cand['type']}")
    print(f"  - Top Candidate URL:      {top_cand['url']}")
    print()

    # Step 4: Phase 4 Canonicalization & SHA-256 Fingerprint
    print("[STAGE 4] Generating Phase 4 Deterministic Canonical SHA-256 Fingerprint...")
    canonical_json = create_canonical_representation(top_cand)
    sha256_hash = generate_sha256_fingerprint(canonical_json)
    print(f"✓ Canonical JSON: {canonical_json}")
    print(f"✓ SHA-256 Digest: {sha256_hash}")
    print()

    # Step 5: Polygon Amoy On-Chain Anchoring
    print("[STAGE 5] Anchoring SHA-256 Fingerprint on Polygon Amoy Smart Contract...")
    client = BlockchainAnchorClient()
    client.validate_connection()
    anchor_rec = client.anchor_fingerprint(sha256_hash)
    
    print(f"✓ Network:          {anchor_rec['network']} (Chain ID: {anchor_rec['chain_id']})")
    print(f"✓ Contract Address: {anchor_rec['contract_address']}")
    print(f"✓ Transaction Hash: {anchor_rec['transaction_hash']}")
    print(f"✓ Confirmed Block:  #{anchor_rec['block_number']}")
    print(f"✓ Anchored By:      {anchor_rec['anchored_by']}")
    print(f"✓ Timestamp:        {anchor_rec['anchored_at_iso']}")
    print(f"✓ On-Chain Status:  {anchor_rec['status']}")
    assert anchor_rec["verification"]["matches_local_hash"] is True
    print()

    # Step 6: Phase 5 Independent Verification & Tamper Detection
    print("[STAGE 6] Performing Phase 5 Independent Verification & Tamper Detection...")
    
    # Check 6A: Original candidate verification
    verif_orig = verify_candidate_integrity(top_cand)
    print(f"✓ Check 6A (Original Candidate -> Live On-Chain Lookup):")
    print(f"  - Calculated Hash: {verif_orig['current_hash']}")
    print(f"  - On-Chain Status: Anchored={verif_orig['blockchain'].get('is_anchored', False)}")
    print(f"  - Block Number:    #{verif_orig['blockchain'].get('block_number')}")
    print(f"  - Verdict:         {verif_orig['status']}")
    assert verif_orig["status"] == "VERIFIED", f"Expected VERIFIED, got {verif_orig['status']}"
    print("  --> Result: ✅ VERIFIED")
    print()

    # Check 6B: Tampered candidate detection (URL modified by 1 character)
    tampered_cand = dict(top_cand)
    tampered_cand["url"] = top_cand["url"][:-1] + ("3" if top_cand["url"][-1] == "2" else "2")
    verif_tamp = verify_candidate_integrity(tampered_cand, expected_hash=sha256_hash)
    print(f"✓ Check 6B (Tampered Candidate -> Avalanche Tamper Detection):")
    print(f"  - Tampered URL:    {tampered_cand['url']}")
    print(f"  - Tampered Hash:   {verif_tamp['current_hash']}")
    print(f"  - Expected Hash:   {verif_tamp['expected_hash']}")
    print(f"  - Hashes Match:    {verif_tamp['hashes_match']}")
    print(f"  - Verdict:         {verif_tamp['status']}")
    assert verif_tamp["status"] == "TAMPERED", "Tamper detection failed!"
    print("  --> Result: ❌ TAMPERED")
    print()

    # Check 6C: Unanchored candidate
    unanc_cand = {
        "title": "Random Unanchored Web Discovery",
        "source": "example.org",
        "url": "https://example.org/random_post_99999",
        "type": "WEB",
        "engine": "Google Lens"
    }
    verif_unanc = verify_candidate_integrity(unanc_cand)
    print(f"✓ Check 6C (Unanchored Candidate -> Registry Lookup):")
    print(f"  - Unanchored Hash: {verif_unanc['current_hash']}")
    print(f"  - On-Chain Status: Anchored={verif_unanc['blockchain'].get('is_anchored', False)}")
    print(f"  - Verdict:         {verif_unanc['status']}")
    assert verif_unanc["status"] == "NOT_ANCHORED", "Unanchored check failed!"
    print("  --> Result: ⚠️ NOT_ANCHORED")
    print()

    print("=" * 60)
    print("END-TO-END PIPELINE VERIFICATION COMPLETED SUCCESSFULLY")
    print("All 5 Stages Genuinely Verified on Polygon Amoy (0 Mocks)")
    print("=" * 60)


if __name__ == "__main__":
    run_e2e_pipeline()
