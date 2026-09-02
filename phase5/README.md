# Phase 5: Blockchain Verification & Tamper Detection
**HH Goa 2026 Shortlisting Challenge — Task 3**

---

## 1. Overview & Architecture

Phase 5 provides an **independent on-chain cryptographic verification and tamper detection engine**. Given a candidate social/web discovery, it re-calculates the deterministic canonical SHA-256 fingerprint and queries the `DataAnchor` smart contract on the **Polygon Amoy Testnet (Chain ID: 80002)**.

```
Current Candidate JSON
        │
        ▼
Phase 4 Deterministic Canonical Serialization
        │
        ▼
Current SHA-256 Digest (64-character Hex)
        │
        ▼
Query Polygon Amoy Testnet (Web3.py)
        │
        ├── isHashAnchored(expected_hash) ──► On-Chain State (Block, Timestamp, Submitter)
        │
        ▼
Tri-State Verdict Evaluation:
  ├── ✅ VERIFIED    : current_hash == expected_hash AND expected_hash is anchored on-chain
  ├── ❌ TAMPERED    : current_hash != expected_hash AND expected_hash is anchored on-chain
  └── ⚠️ NOT_ANCHORED: target fingerprint is not recorded in the on-chain registry
        │
        ▼
Structured Verification Result Saved to phase5/output/verification_result.json
```

---

## 2. Security & Verification Principles

1. **Zero Trust in Local Records**: The system never relies solely on local JSON files (`blockchain_record.json`). The blockchain itself is queried as the immutable single source of truth.
2. **True Tamper Detection**: When validating against an expected anchored fingerprint, any subtle modification (even a single character in a URL or title) changes the SHA-256 digest via the avalanche effect. If the expected hash exists on-chain but the current data hash differs, the record is flagged as `❌ TAMPERED`.
3. **Deterministic Canonicalization**: Sorts JSON keys and fixes compact delimiters (`","`, `":"`) ensuring exact reproducibility across any programming language.

---

## 3. Directory Structure

```
phase5/
├── verify_integrity.py     # Main verification and tamper detection CLI
├── requirements.txt        # Combined Web3 requirements
├── README.md               # Architecture, usage, and verification guide
├── test_suite.py           # Automated test suite
├── test_data/              # Test candidate payloads
│   ├── original_candidate.json    # Canonical hash: 1cfb6fbe...
│   ├── tampered_candidate.json    # Modified URL: 6898ac57...
│   └── unanchored_candidate.json  # Unregistered hash: 3c35a5a1...
└── output/
    └── verification_result.json   # Output verification record
```

---

## 4. Setup & Environment

Ensure `.env` in the workspace root contains the Polygon Amoy testnet configuration:

```env
BLOCKCHAIN_RPC_URL=https://polygon-amoy-bor-rpc.publicnode.com
BLOCKCHAIN_CHAIN_ID=80002
BLOCKCHAIN_CONTRACT_ADDRESS=0xeb4FA1693171e3d2E7DF42D861453cf6B47CB71D
```

Install dependencies:
```bash
pip install -r phase5/requirements.txt
```

---

## 5. Running the Automated Test Suite

```bash
python phase5/test_suite.py
```

**Real Test Output (Polygon Amoy Testnet):**
```text
========================================
PHASE 5 AUTOMATED TEST SUITE
========================================
✓ Test 1: Deterministic original hashing (SHA-256): PASS
  Hash: 1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4
✓ Test 2: Tampered candidate divergence (SHA-256): PASS
  Modified Hash: 6898ac577a4408f72254393521ce56481f6a0079356b08dae985dc806fb98e37
✓ Test 3: Unanchored candidate fingerprint generation: PASS
  Unanchored Hash: 3c35a5a11c81f2f6ba1c4b1ae0a4ca87a9c8e780cacd031ad7c8dc6eb3540f51
✓ Test 4: Live RPC connectivity to Polygon Amoy (Block #46514339): PASS
✓ Test 5: Missing file error handling: PASS
✓ Test 6: Invalid JSON error handling: PASS
✓ Test 7: Original candidate on-chain verification (VERIFIED): PASS
  Anchored Block: #46513999
✓ Test 8: Tampered candidate divergence evaluation (TAMPERED): PASS
✓ Test 9: Unanchored candidate evaluation (NOT_ANCHORED): PASS

========================================
ALL PHASE 5 TESTS COMPLETED SUCCESSFULLY (9/9)
========================================
```

---

## 6. CLI Usage & Verification Scenarios

### Scenario A: Original Candidate Verification
```bash
python phase5/verify_integrity.py --input phase5/test_data/original_candidate.json
```
```text
========================================
PHASE 5 - BLOCKCHAIN VERIFICATION
========================================

Input candidate:
phase5/test_data/original_candidate.json

Current SHA-256 Fingerprint:
1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4

Expected/Anchored Fingerprint:
1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4

Blockchain Query (Polygon Amoy):
- Chain ID:  80002
- Contract:  0xeb4FA1693171e3d2E7DF42D861453cf6B47CB71D
- Anchored:  True
- Block:     #46513999
- Submitter: 0xd0a8547503500b8307eb34e4800Ff2e3157F6030
- Timestamp: 2026-09-02T07:00:41+00:00

Result:
✅ VERIFIED
   The current candidate data produces exactly the same SHA-256 fingerprint as the blockchain-anchored fingerprint.

========================================
```

### Scenario B: Tamper Detection Verification
```bash
python phase5/verify_integrity.py \
    --input phase5/test_data/tampered_candidate.json \
    --expected-hash 1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4
```
```text
========================================
PHASE 5 - BLOCKCHAIN VERIFICATION
========================================

Input candidate:
phase5/test_data/tampered_candidate.json

Current SHA-256 Fingerprint:
6898ac577a4408f72254393521ce56481f6a0079356b08dae985dc806fb98e37

Expected/Anchored Fingerprint:
1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4

Blockchain Query (Polygon Amoy):
- Chain ID:  80002
- Contract:  0xeb4FA1693171e3d2E7DF42D861453cf6B47CB71D
- Anchored:  True
- Block:     #46513999
- Submitter: 0xd0a8547503500b8307eb34e4800Ff2e3157F6030
- Timestamp: 2026-09-02T07:00:41+00:00

Result:
❌ TAMPERED
   The current candidate data produces a different SHA-256 fingerprint from the blockchain-anchored fingerprint.

========================================
```

### Scenario C: Direct Hash Query
```bash
python phase5/verify_integrity.py --hash 1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4
```

### Scenario D: JSON Output Format
```bash
python phase5/verify_integrity.py --input phase5/test_data/original_candidate.json --json
```

---

## 7. Verification Output Format (`verification_result.json`)

Saved automatically to `phase5/output/verification_result.json`:

```json
{
  "status": "VERIFIED",
  "summary": "The current candidate data produces exactly the same SHA-256 fingerprint as the blockchain-anchored fingerprint.",
  "current_hash": "1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4",
  "expected_hash": "1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4",
  "hashes_match": true,
  "blockchain": {
    "network": "Polygon Amoy",
    "chain_id": 80002,
    "contract_configured": true,
    "contract_address": "0xeb4FA1693171e3d2E7DF42D861453cf6B47CB71D",
    "is_anchored": true,
    "block_number": 46513999,
    "anchored_at_timestamp": 1788332441,
    "anchored_at_iso": "2026-09-02T07:00:41+00:00",
    "anchored_by": "0xd0a8547503500b8307eb34e4800Ff2e3157F6030"
  },
  "candidate_data": {
    "title": "So is emin watching gree and böcü or #Arafta #EmSu",
    "source": "x.com",
    "url": "https://x.com/lorrainevc/status/2083252779527852252",
    "type": "SOCIAL"
  },
  "verified_at": "2026-09-02T07:04:22+00:00"
}
```

---

## 8. Live On-Chain Contract & Verification Evidence

- **Network**: Polygon Amoy Testnet (Chain ID: `80002`)
- **Contract Address**: `0xeb4FA1693171e3d2E7DF42D861453cf6B47CB71D`
- **Deployment Tx**: `0xb799eb6e3e63be90c6e2a2a31e3e565d6a5c517745e5919473e09fb44069619b`
- **Anchored Digest**: `1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4`
- **Anchored Block**: `#46513999`
- **Submitter**: `0xd0a8547503500b8307eb34e4800Ff2e3157F6030`
