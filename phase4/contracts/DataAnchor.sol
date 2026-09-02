// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DataAnchor
 * @dev Simple, gas-efficient on-chain cryptographic anchor for SHA-256 fingerprints.
 * Anchors tamper-evident hashes with sender address, timestamp, and block number.
 */
contract DataAnchor {
    event HashAnchored(
        bytes32 indexed fingerprint,
        address indexed submitter,
        uint256 timestamp,
        uint256 blockNumber
    );

    mapping(bytes32 => uint256) public anchoredBlock;
    mapping(bytes32 => uint256) public anchoredTimestamp;
    mapping(bytes32 => address) public anchoredBy;

    function anchorHash(bytes32 fingerprint) external returns (bool) {
        require(anchoredBlock[fingerprint] == 0, "Fingerprint already anchored");
        anchoredBlock[fingerprint] = block.number;
        anchoredTimestamp[fingerprint] = block.timestamp;
        anchoredBy[fingerprint] = msg.sender;
        emit HashAnchored(fingerprint, msg.sender, block.timestamp, block.number);
        return true;
    }

    function isHashAnchored(bytes32 fingerprint)
        external
        view
        returns (
            bool isAnchored,
            uint256 blockNumber,
            uint256 timestamp,
            address submitter
        )
    {
        return (
            anchoredBlock[fingerprint] > 0,
            anchoredBlock[fingerprint],
            anchoredTimestamp[fingerprint],
            anchoredBy[fingerprint]
        );
    }
}
