# Phase 4: Blockchain Anchoring & Cryptographic Verification
**HH Goa 2026 Shortlisting Challenge — Task 3**

---

## 1. Overview & Architecture

Phase 4 takes a verified social/web discovery from Phase 3, serializes the metadata into a canonical deterministic JSON format, computes a 256-bit SHA-256 cryptographic digest, and anchors this fingerprint permanently onto an EVM-compatible public testnet (**Polygon Amoy Testnet**, Chain ID: `80002`).

```
Phase 3 Matched Candidate
        │
        ▼
Canonical JSON Normalization (Sorted keys, compact delimiters)
        │
        ▼
Cryptographic Digest: SHA-256 (64-char Hex / 32-byte Word)
        │
        ▼
Web3.py Client (Polygon Amoy Testnet)
        ├── Option A: DataAnchor Smart Contract (anchorHash(bytes32))
        └── Option B: Direct Immutable Calldata Transaction (data=0x<hash>)
        │
        ▼
Transaction Broadcast & Block Confirmation (~2-5s)
        │
        ▼
Independent On-Chain Verification (stored_hash == local_hash)
        │
        ▼
Persistent Record Saved to phase4/output/blockchain_record.json
```

---

## 2. Design & Privacy Rationale

### Why Blockchain?
- **Tamper-Evident Proof of Discovery**: Once mined into a block, the record cannot be retroactively altered, backdated, or deleted by any party.
- **Decentralized Verification**: Anyone with an RPC node or block explorer can independently verify that a specific discovery existed at a specific block number and timestamp.

### Why SHA-256?
- Standard, collision-resistant cryptographic hash function.
- Produces a 32-byte digest (`bytes32`), matching the native word size of the Ethereum Virtual Machine (EVM), minimizing gas consumption.

### On-Chain vs Off-Chain Data Separation:
- **Stored On-Chain**:
  - 32-byte SHA-256 cryptographic fingerprint (`bytes32`)
  - Submitter wallet address (`address`)
  - Block timestamp and block number (`uint256`)
- **Kept Strictly Off-Chain**:
  - Full candidate metadata (raw post title, URLs, image URLs)
  - Raw facial scans and 512-D face embedding vectors
  - Search query history and IP metadata

---

## 3. Directory Structure

```
phase4/
├── blockchain_anchor.py    # Main Web3.py anchoring engine & CLI
├── requirements.txt        # Dependencies: web3, eth-account, python-dotenv
├── .env.example            # Environment configuration template
├── README.md               # Architecture, setup, and verification guide
├── contracts/
│   ├── DataAnchor.sol      # Solidity smart contract
│   └── DataAnchor.json     # Compiled contract ABI & EVM deployment bytecode
├── test_data/              # Test candidate payloads
│   ├── sample_candidate.json
│   ├── sample_candidate_modified.json
│   └── invalid.json
└── output/
    └── blockchain_record.json # Final on-chain verified record
```

---

## 4. Setup & Configuration

### Step 1: Install Dependencies
```bash
pip install -r phase4/requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy phase4\.env.example .env
```

Ensure `.env` contains:
```env
BLOCKCHAIN_RPC_URL=https://polygon-amoy-bor-rpc.publicnode.com
BLOCKCHAIN_PRIVATE_KEY=your_testnet_private_key_here
BLOCKCHAIN_CHAIN_ID=80002
BLOCKCHAIN_CONTRACT_ADDRESS=
```

---

## 5. Wallet Setup & Testnet Faucets

### Generate a New Testnet Burner Wallet:
```bash
python phase4/blockchain_anchor.py --generate-wallet
```
This generates a new EVM address and private key.

### Free Testnet Faucets for Polygon Amoy (POL):
1. **Polygon Official Faucet**: [https://faucet.polygon.technology/](https://faucet.polygon.technology/)
2. **Google Cloud Web3 Faucet**: [https://cloud.google.com/application/web3/faucet/ethereum/amoy](https://cloud.google.com/application/web3/faucet/ethereum/amoy)
3. **Chainlink Faucet**: [https://faucets.chain.link/polygon-amoy](https://faucets.chain.link/polygon-amoy)

*A tiny amount (0.01 POL) is sufficient for hundreds of anchoring transactions.*

---

## 6. Smart Contract Deployment (Optional)

To deploy a dedicated `DataAnchor` contract to Polygon Amoy:
```bash
python phase4/blockchain_anchor.py --deploy-contract
```
Copy the returned `Contract Address` into `BLOCKCHAIN_CONTRACT_ADDRESS` in `.env`.

*(If `BLOCKCHAIN_CONTRACT_ADDRESS` is omitted, the module automatically uses direct on-chain calldata anchoring).*

---

## 7. CLI Usage & Verification Examples

### 1. Anchor a Phase 3 Candidate Discovery:
```bash
python phase4/blockchain_anchor.py --input phase4/test_data/sample_candidate.json
```

**Real On-Chain Output (Polygon Amoy Testnet):**
```text
========================================
PHASE 4 - BLOCKCHAIN ANCHORING
========================================

✓ Phase 3 candidate loaded
✓ Canonical data generated
✓ SHA-256 fingerprint generated
✓ Connected to Polygon Amoy testnet
✓ Transaction submitted
✓ Transaction confirmed
✓ ON-CHAIN HASH VERIFIED

Fingerprint:
1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4

Transaction hash:
0xb799eb6e3e63be90c6e2a2a31e3e565d6a5c517745e5919473e09fb44069619b

Block number:
46513999

Network:
Polygon Amoy

Status:
✓ BLOCKCHAIN ANCHORED

========================================
```

### 2. Output as Structured JSON:
```bash
python phase4/blockchain_anchor.py --input phase4/test_data/sample_candidate.json --json
```

### 3. Direct Self-Test:
```bash
python phase4/test_suite.py
```

---

## 8. On-Chain Verification Record (`blockchain_record.json`)

When an anchoring transaction completes, the record is saved to `phase4/output/blockchain_record.json`:

```json
{
  "schema_version": "1.0",
  "fingerprint_algorithm": "SHA-256",
  "fingerprint": "1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4",
  "network": "Polygon Amoy",
  "chain_id": 80002,
  "transaction_hash": "0xb799eb6e3e63be90c6e2a2a31e3e565d6a5c517745e5919473e09fb44069619b",
  "block_number": 46513999,
  "contract_address": "0xeb4FA1693171e3d2E7DF42D861453cf6B47CB71D",
  "anchored_by": "0xd0a8547503500b8307eb34e4800Ff2e3157F6030",
  "anchored_at_timestamp": 1788332441,
  "anchored_at_iso": "2026-09-02T07:00:41+00:00",
  "status": "ANCHORED",
  "verification": {
    "on_chain_hash": "1cfb6fbe4dd2ba8de4904729dda64011bafff57683e2c351d2a82f1826ee90a4",
    "matches_local_hash": true,
    "verified_at": "2026-09-02T07:04:22+00:00"
  },
  "candidate_summary": {
    "title": "So is emin watching gree and böcü or #Arafta #EmSu",
    "source": "x.com",
    "url": "https://x.com/lorrainevc/status/2083252779527852252",
    "type": "SOCIAL"
  }
}
```

---

## 9. Error Handling

| Condition | Exception | CLI Behavior |
| :--- | :--- | :--- |
| Missing Input File | `InvalidInputDataError` | Clean message `[ERROR: FILE NOT FOUND]` (exit code 2) |
| Invalid JSON Format | `InvalidInputDataError` | Clean message `[ERROR: INVALID JSON]` (exit code 2) |
| Missing Credentials | `MissingBlockchainCredentialsError` | Clear setup instructions (exit code 3) |
| Zero Testnet Balance | `InsufficientFundsError` | Informs user and provides faucet links (exit code 4) |
| RPC Connection Failure | `RpcConnectionError` | Catches network issue without fake success (exit code 5) |
| Transaction Reverted | `TransactionRevertError` | Reports on-chain revert reason (exit code 6) |
| On-Chain Hash Mismatch | `VerificationMismatchError` | Alerts if on-chain data != local hash (exit code 7) |
