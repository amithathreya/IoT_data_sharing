// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract TelemetryRegistry {
    struct TelemetryRecord {
        string nodeId;
        uint256 timestamp;
        bytes32 payloadHash;
    }

    // Mapping from node ID to an array of their telemetry records
    mapping(string => TelemetryRecord[]) public nodeRecords;
    uint256 public totalRecords;

    event TelemetryRecorded(
        string nodeId,
        uint256 timestamp,
        bytes32 payloadHash
    );

    function getRecordCount() public view returns (uint256) {
        return totalRecords;
    }

    function recordTelemetry(string memory _nodeId, uint256 _timestamp, bytes32 _payloadHash) public {
        TelemetryRecord memory newRecord = TelemetryRecord({
            nodeId: _nodeId,
            timestamp: _timestamp,
            payloadHash: _payloadHash
        });

        nodeRecords[_nodeId].push(newRecord);
        totalRecords += 1;

        emit TelemetryRecorded(_nodeId, _timestamp, _payloadHash);
    }
}
