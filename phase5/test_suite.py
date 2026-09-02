#!/usr/bin/env python3
"""
Automated Test Suite for Phase 5: Blockchain Verification & Tamper Detection
HH Goa 2026 Shortlisting Challenge
"""

import os
import sys
import json
import subprocess
from web3 import Web3

# Add workspace to path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from phase4.blockchain_anchor import (
    create_canonical_representation,
    generate_sha256_fingerprint
)
from phase5.verify_integrity import (
    BlockchainVerifier,
    verify_candidate_integrity
)


def run_tests():
    print("========================================")
    print("PHASE 5 AUTOMATED TEST SUITE")
    print("========================================")

    # 1. Deterministic Re-Hashing Verification
    with open("phase5/test_data/original_candidate.json", "r", encoding="utf-8") as f:
        orig = json.load(f)

    canon_orig = create_canonical_representation(orig)
    orig_hash = generate_sha256_fingerprint(canon_orig)
    expected_orig_hash = "1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4"
    assert orig_hash == expected_orig_hash, f"Hash mismatch: {orig_hash} != {expected_orig_hash}"
    print(f"✓ Test 1: Deterministic original hashing (SHA-256): PASS\n  Hash: {orig_hash}")

    # 2. Tampered Candidate Hash Verification
    with open("phase5/test_data/tampered_candidate.json", "r", encoding="utf-8") as f:
        tamp = json.load(f)

    canon_tamp = create_canonical_representation(tamp)
    tamp_hash = generate_sha256_fingerprint(canon_tamp)
    expected_tamp_hash = "6898ac577a4408f72254393521ce56481f6a0079356b08dae985dc806fb98e37"
    assert tamp_hash == expected_tamp_hash, f"Tampered hash mismatch: {tamp_hash} != {expected_tamp_hash}"
    assert orig_hash != tamp_hash, "Original and tampered hashes must not match!"
    print(f"✓ Test 2: Tampered candidate divergence (SHA-256): PASS\n  Modified Hash: {tamp_hash}")

    # 3. Unanchored Candidate Hash Verification
    with open("phase5/test_data/unanchored_candidate.json", "r", encoding="utf-8") as f:
        unanc = json.load(f)
    canon_unanc = create_canonical_representation(unanc)
    unanc_hash = generate_sha256_fingerprint(canon_unanc)
    print(f"✓ Test 3: Unanchored candidate fingerprint generation: PASS\n  Unanchored Hash: {unanc_hash}")

    # 4. Polygon Amoy RPC Connectivity Check
    verifier = BlockchainVerifier()
    verifier.validate_connection()
    block = verifier.w3.eth.block_number
    assert block > 0, "Failed to retrieve block number from Polygon Amoy!"
    print(f"✓ Test 4: Live RPC connectivity to Polygon Amoy (Block #{block}): PASS")

    # 5. Missing Input File Error Handling
    res = subprocess.run(
        ["python", "phase5/verify_integrity.py", "--input", "phase5/test_data/non_existent.json"],
        capture_output=True, text=True
    )
    assert res.returncode != 0 and "[ERROR: FILE NOT FOUND]" in res.stderr
    print("✓ Test 5: Missing file error handling: PASS")

    # 6. Invalid JSON Error Handling
    res = subprocess.run(
        ["python", "phase5/verify_integrity.py", "--input", "phase4/test_data/invalid.json"],
        capture_output=True, text=True
    )
    assert res.returncode != 0 and "[ERROR: INVALID JSON]" in res.stderr
    print("✓ Test 6: Invalid JSON error handling: PASS")

    # 7. Tamper Detection Logic Evaluation
    # Verification with original candidate against on-chain smart contract
    res_orig = verify_candidate_integrity(orig)
    assert res_orig["status"] == "VERIFIED", f"Expected VERIFIED, got {res_orig['status']}"
    assert res_orig["blockchain"]["is_anchored"] is True
    print(f"✓ Test 7: Original candidate on-chain verification (VERIFIED): PASS")
    print(f"  Anchored Block: #{res_orig['blockchain']['block_number']}")

    # Verification with tampered candidate against expected hash
    res_tamp = verify_candidate_integrity(tamp, expected_hash=orig_hash)
    assert res_tamp["status"] == "TAMPERED", f"Expected TAMPERED, got {res_tamp['status']}"
    assert res_tamp["hashes_match"] is False
    print(f"✓ Test 8: Tampered candidate divergence evaluation (TAMPERED): PASS")

    # Verification with unanchored status
    res_unanc = verify_candidate_integrity(unanc)
    assert res_unanc["status"] == "NOT_ANCHORED"
    print(f"✓ Test 9: Unanchored candidate evaluation (NOT_ANCHORED): PASS")

    print("\n========================================")
    print("ALL PHASE 5 TESTS COMPLETED SUCCESSFULLY (9/9)")
    print("========================================")


if __name__ == "__main__":
    run_tests()
