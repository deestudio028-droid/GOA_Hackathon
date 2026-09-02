#!/usr/bin/env python3
"""
Automated Test Suite for Phase 4: Blockchain Anchoring
HH Goa 2026 Shortlisting Challenge
"""

import os
import sys
import json
import subprocess
import hashlib
from web3 import Web3

# Add workspace to path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from phase4.blockchain_anchor import (
    create_canonical_representation,
    generate_sha256_fingerprint,
    BlockchainAnchorClient
)

def run_tests():
    print("========================================")
    print("PHASE 4 AUTOMATED TEST SUITE")
    print("========================================")

    # Test 1: Canonical Serialization Determinism
    with open("phase4/test_data/sample_candidate.json", "r", encoding="utf-8") as f:
        cand1 = json.load(f)

    canon1 = create_canonical_representation(cand1)
    canon2 = create_canonical_representation(cand1)
    hash1 = generate_sha256_fingerprint(canon1)
    hash2 = generate_sha256_fingerprint(canon2)

    assert hash1 == hash2, "Deterministic hashing failed!"
    print("✓ Test 1: Deterministic canonical hashing: PASS")
    print(f"  Hash: {hash1}")

    # Test 2: Avalanche Effect (1-character modification)
    with open("phase4/test_data/sample_candidate_modified.json", "r", encoding="utf-8") as f:
        cand_mod = json.load(f)

    canon_mod = create_canonical_representation(cand_mod)
    hash_mod = generate_sha256_fingerprint(canon_mod)

    assert hash1 != hash_mod, "Avalanche effect test failed!"
    print("✓ Test 2: Avalanche effect verification: PASS")
    print(f"  Modified Hash: {hash_mod}")

    # Test 3: RPC Connectivity to Polygon Amoy
    client = BlockchainAnchorClient()
    client.validate_connection()
    network = client.get_network_name()
    block = client.w3.eth.block_number
    assert block > 0, "Failed to retrieve block number!"
    print(f"✓ Test 3: Real RPC connectivity to {network} (Block #{block}): PASS")

    # Test 4: Missing File Error Handling
    res = subprocess.run(
        ["python", "phase4/blockchain_anchor.py", "--input", "phase4/test_data/non_existent.json"],
        capture_output=True, text=True
    )
    assert res.returncode != 0 and "[ERROR: FILE NOT FOUND]" in res.stderr
    print("✓ Test 4: Missing file error handling: PASS")

    # Test 5: Invalid JSON Error Handling
    res = subprocess.run(
        ["python", "phase4/blockchain_anchor.py", "--input", "phase4/test_data/invalid.json"],
        capture_output=True, text=True
    )
    assert res.returncode != 0 and "[ERROR: INVALID JSON]" in res.stderr
    print("✓ Test 5: Invalid JSON error handling: PASS")

    # Test 6: Missing Credentials Error Handling
    env_clean = dict(os.environ)
    env_clean["BLOCKCHAIN_PRIVATE_KEY"] = ""
    res = subprocess.run(
        ["python", "phase4/blockchain_anchor.py", "--test"],
        capture_output=True, text=True, env=env_clean
    )
    assert res.returncode != 0 and "[ERROR: MISSING BLOCKCHAIN CREDENTIALS]" in res.stderr
    print("✓ Test 6: Missing credentials error handling: PASS")

    # Test 7: On-Chain Contract State Verification
    rec = client.anchor_fingerprint(hash1)
    assert rec["verification"]["matches_local_hash"] is True
    print(f"✓ Test 7: On-Chain contract state verification ({rec['contract_address']}): PASS")
    print(f"  Anchored Block: #{rec['block_number']}")

    print("\n========================================")
    print("ALL INTEGRATION TESTS PASSED (7/7)")
    print("========================================")

if __name__ == "__main__":
    run_tests()
