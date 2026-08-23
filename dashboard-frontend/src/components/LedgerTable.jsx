import React from 'react';

export default function LedgerTable({ transactions }) {
  if (transactions.length === 0) {
    return (
      <div style={{ padding: '20px', color: 'var(--text-secondary)', textAlign: 'center' }}>
        No blockchain transactions logged yet...
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="ledger-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Node</th>
            <th>Tx Hash</th>
            <th>Payload Hash</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx, idx) => (
            <tr key={`${tx.tx_hash}-${idx}`}>
              <td style={{ color: 'var(--text-secondary)' }}>
                {new Date(tx.timestamp).toLocaleTimeString()}
              </td>
              <td>{tx.node_id}</td>
              <td className="hash-cell" title={tx.tx_hash}>
                {tx.tx_hash.substring(0, 10)}...{tx.tx_hash.substring(tx.tx_hash.length - 8)}
              </td>
              <td className="hash-cell" title={tx.payload_hash}>
                {tx.payload_hash.substring(0, 10)}...{tx.payload_hash.substring(tx.payload_hash.length - 8)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
