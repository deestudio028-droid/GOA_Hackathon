#!/usr/bin/env python3
"""
==============================================================================
Task 3 - Phase 5: Blockchain Verification & Tamper Detection Module
HH Goa 2026 Shortlisting Challenge

This module performs independent on-chain cryptographic verification and
tamper detection by:
1. Re-calculating the deterministic canonical SHA-256 fingerprint of a candidate.
2. Independently querying the DataAnchor smart contract on Polygon Amoy testnet.
3. Evaluating tamper evidence:
   - ✅ VERIFIED: Current hash == Expected hash AND Expected hash is anchored.
   - ❌ TAMPERED: Current hash != Expected hash AND Expected hash is anchored.
   - ⚠️ NOT_ANCHORED: Fingerprint is not anchored on-chain.

NO mock data, NO simulated verification.
==============================================================================
"""

import os
import sys
import io
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

# Ensure UTF-8 output encoding for cross-platform terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add workspace root to sys.path to enable direct modular imports from phase4
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from dotenv import load_dotenv
from web3 import Web3

# Import existing modular components from Phase 4
try:
    from phase4.blockchain_anchor import (
        create_canonical_representation,
        generate_sha256_fingerprint,
        DATA_ANCHOR_ABI,
        BlockchainAnchorClient,
        BlockchainAnchorError,
        InvalidInputDataError,
        MissingBlockchainCredentialsError,
        RpcConnectionError
    )
except ImportError as e:
    raise ImportError(f"Failed to import Phase 4 blockchain module: {e}")

# Load environment variables (authoritative root .env first)
root_env = os.path.join(WORKSPACE_ROOT, ".env")
if os.path.exists(root_env):
    load_dotenv(dotenv_path=root_env, override=True)
load_dotenv(override=False)


# ==============================================================================
# Blockchain Verifier Client
# ==============================================================================

class BlockchainVerifier:
    """Queries Polygon Amoy testnet to verify on-chain fingerprint existence and metadata."""

    DEFAULT_AMOY_RPC = "https://polygon-amoy-bor-rpc.publicnode.com"
    DEFAULT_AMOY_CHAIN_ID = 80002

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        chain_id: Optional[int] = None
    ):
        self.rpc_url = rpc_url or os.getenv("BLOCKCHAIN_RPC_URL") or self.DEFAULT_AMOY_RPC
        self.contract_address = contract_address or os.getenv("BLOCKCHAIN_CONTRACT_ADDRESS")
        env_chain_id = os.getenv("BLOCKCHAIN_CHAIN_ID")
        self.chain_id = chain_id or (int(env_chain_id) if env_chain_id else self.DEFAULT_AMOY_CHAIN_ID)

        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 20}))
            from web3.middleware import geth_poa_middleware
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception as e:
            raise RpcConnectionError(f"Failed to initialize Web3 provider for '{self.rpc_url}': {e}")

    def validate_connection(self) -> None:
        """Verifies active connectivity to RPC."""
        if not self.w3.is_connected():
            raise RpcConnectionError(
                f"Cannot connect to blockchain RPC endpoint: {self.rpc_url}\n"
                "Please verify your internet connection or BLOCKCHAIN_RPC_URL in .env."
            )

    def get_network_name(self) -> str:
        if self.chain_id == 80002:
            return "Polygon Amoy"
        elif self.chain_id == 11155111:
            return "Ethereum Sepolia"
        elif self.chain_id == 84532:
            return "Base Sepolia"
        elif self.chain_id == 421614:
            return "Arbitrum Sepolia"
        elif self.chain_id == 137:
            return "Polygon Mainnet"
        return f"EVM Network (Chain ID {self.chain_id})"

    def query_anchor_status(self, fingerprint_hex: str) -> Dict[str, Any]:
        """
        Queries the on-chain DataAnchor smart contract for the given 64-char hex fingerprint.
        Returns dictionary with on-chain status, block number, timestamp, and submitter.
        """
        self.validate_connection()

        fp = fingerprint_hex.strip().lower()
        if len(fp) != 64 or not all(c in "0123456789abcdef" for c in fp):
            raise ValueError(f"Invalid SHA-256 fingerprint format: '{fp}'")

        if not self.contract_address or not Web3.is_address(self.contract_address):
            return {
                "network": self.get_network_name(),
                "chain_id": self.chain_id,
                "contract_configured": False,
                "contract_address": None,
                "is_anchored": False,
                "error": "BLOCKCHAIN_CONTRACT_ADDRESS is not configured in .env or arguments."
            }

        checksum_addr = Web3.to_checksum_address(self.contract_address)
        
        # Verify contract bytecode exists at address
        code = self.w3.eth.get_code(checksum_addr)
        if not code or len(code) == 0:
            return {
                "network": self.get_network_name(),
                "chain_id": self.chain_id,
                "contract_configured": True,
                "contract_address": checksum_addr,
                "is_anchored": False,
                "error": f"No contract bytecode deployed at address {checksum_addr} on {self.get_network_name()}."
            }

        contract = self.w3.eth.contract(address=checksum_addr, abi=DATA_ANCHOR_ABI)
        fp_bytes32 = bytes.fromhex(fp)

        try:
            is_anchored, blk, ts, submitter = contract.functions.isHashAnchored(fp_bytes32).call()
        except Exception as e:
            raise RpcConnectionError(f"Error querying DataAnchor contract at {checksum_addr}: {e}")

        return {
            "network": self.get_network_name(),
            "chain_id": self.chain_id,
            "contract_configured": True,
            "contract_address": checksum_addr,
            "is_anchored": bool(is_anchored),
            "block_number": int(blk) if is_anchored else None,
            "anchored_at_timestamp": int(ts) if is_anchored else None,
            "anchored_at_iso": datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat() if (is_anchored and ts > 0) else None,
            "anchored_by": submitter if (is_anchored and submitter != "0x0000000000000000000000000000000000000000") else None
        }


# ==============================================================================
# Verification & Tamper Detection Core Engine
# ==============================================================================

def verify_candidate_integrity(
    candidate_data: Dict[str, Any],
    expected_hash: Optional[str] = None,
    contract_address: Optional[str] = None,
    rpc_url: Optional[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Independently verifies candidate data integrity against the blockchain:
    1. Computes current canonical SHA-256 fingerprint.
    2. Resolves expected/anchored hash (from arg, record file, or current hash).
    3. Queries Polygon Amoy smart contract.
    4. Evaluates VERIFIED / TAMPERED / NOT_ANCHORED.
    5. Saves structured verification result to output_path.
    """
    # Step 1: Compute current canonical SHA-256 fingerprint
    canonical_json = create_canonical_representation(candidate_data)
    current_hash = generate_sha256_fingerprint(canonical_json)

    # Step 2: Determine target lookup hash
    if expected_hash and expected_hash.strip():
        target_lookup_hash = expected_hash.strip().lower()
        has_explicit_expected = True
    else:
        target_lookup_hash = current_hash.strip().lower()
        has_explicit_expected = False

    # Step 3: Query Polygon Amoy blockchain
    verifier = BlockchainVerifier(rpc_url=rpc_url, contract_address=contract_address)
    on_chain_status = verifier.query_anchor_status(target_lookup_hash)

    # Step 4: Determine verification verdict
    is_anchored = on_chain_status.get("is_anchored", False)
    hashes_match = (current_hash.lower() == target_lookup_hash.lower())

    if is_anchored:
        if hashes_match:
            verdict = "VERIFIED"
            summary_message = "The current candidate data produces exactly the same SHA-256 fingerprint as the blockchain-anchored fingerprint."
        else:
            verdict = "TAMPERED"
            summary_message = "The current candidate data produces a different SHA-256 fingerprint from the blockchain-anchored fingerprint."
    else:
        if has_explicit_expected and not hashes_match:
            verdict = "TAMPERED"
            summary_message = f"TAMPERED: Current candidate fingerprint ({current_hash}) differs from expected fingerprint ({target_lookup_hash})."
        else:
            verdict = "NOT_ANCHORED"
            summary_message = "The target fingerprint was not found in the on-chain DataAnchor registry."

    result_payload = {
        "status": verdict,
        "summary": summary_message,
        "current_hash": current_hash,
        "expected_hash": target_lookup_hash,
        "hashes_match": hashes_match,
        "blockchain": on_chain_status,
        "candidate_data": {
            "title": candidate_data.get("title", ""),
            "source": candidate_data.get("source", ""),
            "url": candidate_data.get("url", ""),
            "type": candidate_data.get("type", "WEB")
        },
        "verified_at": datetime.now(timezone.utc).isoformat()
    }

    # Step 5: Save verification result
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "verification_result.json")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2, ensure_ascii=False)

    return result_payload


# ==============================================================================
# CLI Formatting & Terminal Display
# ==============================================================================

def display_verification_result(result: Dict[str, Any], input_path: Optional[str] = None) -> None:
    """Formats and prints terminal output following the project specification."""
    status = result["status"]

    print("========================================")
    print("PHASE 5 - BLOCKCHAIN VERIFICATION")
    print("========================================")
    print()
    if input_path:
        print(f"Input candidate:\n{input_path}\n")

    print("Current SHA-256 Fingerprint:")
    print(result["current_hash"])
    print()

    print("Expected/Anchored Fingerprint:")
    print(result["expected_hash"])
    print()

    bc = result["blockchain"]
    print(f"Blockchain Query ({bc['network']}):")
    print(f"- Chain ID:  {bc['chain_id']}")
    if bc.get("contract_address"):
        print(f"- Contract:  {bc['contract_address']}")
    print(f"- Anchored:  {bc.get('is_anchored', False)}")
    if bc.get("block_number"):
        print(f"- Block:     #{bc['block_number']}")
    if bc.get("anchored_by"):
        print(f"- Submitter: {bc['anchored_by']}")
    if bc.get("anchored_at_iso"):
        print(f"- Timestamp: {bc['anchored_at_iso']}")
    if bc.get("error"):
        print(f"- Notice:    {bc['error']}")
    print()

    print("Result:")
    if status == "VERIFIED":
        print("✅ VERIFIED")
        print(f"   {result['summary']}")
    elif status == "TAMPERED":
        print("❌ TAMPERED")
        print(f"   {result['summary']}")
    else:
        print("⚠️ NOT_ANCHORED")
        print(f"   {result['summary']}")
    print()
    print("========================================")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 5: Blockchain Verification & Tamper Detection Module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verify_integrity.py --input test_data/original_candidate.json
  python verify_integrity.py --input test_data/tampered_candidate.json --expected-hash <hash>
  python verify_integrity.py --hash <sha256_hex>
  python verify_integrity.py --input test_data/original_candidate.json --json
        """
    )
    parser.add_argument(
        "--input", "-i",
        dest="input_path",
        default=None,
        help="Path to candidate JSON file to verify"
    )
    parser.add_argument(
        "--expected-hash", "-e",
        default=None,
        help="Expected original SHA-256 fingerprint anchored on blockchain"
    )
    parser.add_argument(
        "--hash", "-H",
        dest="direct_hash",
        default=None,
        help="Directly query on-chain status of a 64-character SHA-256 fingerprint"
    )
    parser.add_argument(
        "--contract", "-c",
        default=None,
        help="Override DataAnchor smart contract address"
    )
    parser.add_argument(
        "--rpc", "-r",
        default=None,
        help="Override blockchain RPC endpoint URL"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Custom output path for verification_result.json"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )

    args = parser.parse_args()

    # Determine input data
    candidate_data = None
    if args.direct_hash:
        fp = args.direct_hash.strip().lower()
        if len(fp) != 64 or not all(c in "0123456789abcdef" for c in fp):
            print(f"\n[ERROR: INVALID FINGERPRINT] Expected 64-character SHA-256 hex string, got '{fp}'", file=sys.stderr)
            sys.exit(2)
        candidate_data = {
            "title": "Direct Fingerprint Verification",
            "source": "manual",
            "url": f"urn:sha256:{fp}",
            "type": "UNKNOWN",
            "engine": "Manual"
        }
        expected_hash = fp
    elif args.input_path:
        if not os.path.exists(args.input_path):
            print(f"\n[ERROR: FILE NOT FOUND] Candidate JSON file does not exist at: '{args.input_path}'", file=sys.stderr)
            sys.exit(2)
        try:
            with open(args.input_path, "r", encoding="utf-8") as f:
                candidate_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"\n[ERROR: INVALID JSON] Failed to parse input JSON file '{args.input_path}': {e}", file=sys.stderr)
            sys.exit(2)
        expected_hash = args.expected_hash
    else:
        # Default to test_data/original_candidate.json if available
        default_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data", "original_candidate.json")
        if os.path.exists(default_test):
            with open(default_test, "r", encoding="utf-8") as f:
                candidate_data = json.load(f)
            expected_hash = args.expected_hash
        else:
            parser.print_help()
            print("\nError: Please specify candidate JSON file via --input or a fingerprint via --hash.")
            sys.exit(1)

    try:
        result = verify_candidate_integrity(
            candidate_data=candidate_data,
            expected_hash=expected_hash,
            contract_address=args.contract,
            rpc_url=args.rpc,
            output_path=args.output
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            display_verification_result(result, input_path=args.input_path)

    except RpcConnectionError as e:
        print(f"\n[ERROR: RPC CONNECTION FAILED] {e}", file=sys.stderr)
        sys.exit(3)
    except InvalidInputDataError as e:
        print(f"\n[ERROR: INVALID DATA] {e}", file=sys.stderr)
        sys.exit(4)
    except Exception as e:
        print(f"\n[UNEXPECTED VERIFICATION ERROR] {e}", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    main()
