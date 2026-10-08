// SPDX-License-Identifier: UNLICENSED
// LifelineEvidence records that a Lifeline ledger head existed at a block time. It holds no funds and
// no balances, accepts no payment, and stores no names, amounts, payees or user ids: only the head hash,
// its sequence number, a SHA 256 hash of the user id, the block time, the block number and the sender,
// keyed by head.
pragma solidity >=0.6.10 <0.9.0;

contract LifelineEvidence {
    struct Record {
        bytes32 head;
        uint64 seq;
        bytes32 userHash;
        uint256 timestamp;
        address sender;
        uint256 blockNumber;
    }

    mapping(bytes32 => Record) private records;

    event Anchored(bytes32 indexed head, uint64 seq, bytes32 userHash, uint256 timestamp, address sender);

    function anchor(bytes32 head, uint64 seq, bytes32 userHash) public {
        records[head] = Record(head, seq, userHash, block.timestamp, msg.sender, block.number);
        emit Anchored(head, seq, userHash, block.timestamp, msg.sender);
    }

    // The stored record of a head, or zeros when the head was never anchored.
    function verify(bytes32 head) public view returns (bytes32, uint64, bytes32, uint256, address, uint256) {
        Record memory record = records[head];
        return (record.head, record.seq, record.userHash, record.timestamp, record.sender, record.blockNumber);
    }
}
