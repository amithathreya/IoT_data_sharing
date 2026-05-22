// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract SensorRegistry {
    struct SensorRecord {
        string  nodeId;
        bytes32 payloadHash;
        uint256 timestamp;
        bool    exists;
    }

    mapping(bytes32 => SensorRecord) private records;
    bytes32[] public allHashes;

    event RecordStored(
        string  indexed nodeId,
        bytes32 indexed payloadHash,
        uint256 timestamp
    );

    function storeRecord(
        string  memory nodeId,
        bytes32 payloadHash,
        uint256 timestamp
    ) public {
        require(!records[payloadHash].exists, "Hash already recorded");
        records[payloadHash] = SensorRecord({
            nodeId:      nodeId,
            payloadHash: payloadHash,
            timestamp:   timestamp,
            exists:      true
        });
        allHashes.push(payloadHash);
        emit RecordStored(nodeId, payloadHash, timestamp);
    }

    function verifyRecord(bytes32 payloadHash)
        public view returns (bool)
    {
        return records[payloadHash].exists;
    }

    function getRecord(bytes32 payloadHash)
        public view returns (
            string  memory nodeId,
            bytes32 hash,
            uint256 timestamp,
            bool    exists
        )
    {
        SensorRecord memory r = records[payloadHash];
        return (r.nodeId, r.payloadHash, r.timestamp, r.exists);
    }

    function getTotalRecords() public view returns (uint256) {
        return allHashes.length;
    }
}
