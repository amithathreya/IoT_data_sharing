import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { Activity, ShieldAlert, Cpu, BrainCircuit } from 'lucide-react';
import MetricsChart from './components/MetricsChart';
import LedgerTable from './components/LedgerTable';
import XFLPanel from './components/XFLPanel';

const SOCKET_URL = 'http://localhost:4000';

function App() {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [xflRounds, setXflRounds] = useState([]);

  useEffect(() => {
    const newSocket = io(SOCKET_URL);
    setSocket(newSocket);

    newSocket.on('connect', () => setIsConnected(true));
    newSocket.on('disconnect', () => setIsConnected(false));

    newSocket.on('initial_state', (state) => {
      if (state.transactions) setTransactions(state.transactions.slice(0, 10));
      if (state.xfl_rounds) setXflRounds(state.xfl_rounds);

      const initialAnomalies = [];
      Object.values(state.metrics || {}).forEach(m => {
        if (m.anomaly_class > 0) {
          initialAnomalies.push({
            node_id: m.node_id,
            timestamp: m.ts_ns ? parseInt(m.ts_ns) / 1000000 : Date.now(),
            anomaly_class: m.anomaly_class
          });
        }
      });
      setAnomalies(initialAnomalies.sort((a, b) => b.timestamp - a.timestamp).slice(0, 5));
    });

    newSocket.on('metrics_update', (data) => {
      if (data.node_id) {
        setMetricsHistory(prev => {
          const timeStr = new Date(data.ts_ns ? parseInt(data.ts_ns) / 1000000 : Date.now()).toLocaleTimeString();
          const newPoint = {
            time: timeStr,
            node_id: data.node_id,
            temperature: data.temperature !== 'N/A' ? data.temperature : null,
            humidity: data.humidity !== 'N/A' ? data.humidity : null,
          };
          return [...prev, newPoint].slice(-20);
        });

        if (data.tx_hash) {
          setTransactions(prev => {
            const newTx = {
              node_id: data.node_id,
              tx_hash: data.tx_hash,
              payload_hash: data.payload_hash,
              timestamp: data.ts_ns ? parseInt(data.ts_ns) / 1000000 : Date.now()
            };
            // Only keep latest 10 transactions
            return [newTx, ...prev].slice(0, 10);
          });
        }

        if (data.anomaly_class > 0) {
          setAnomalies(prev => {
            const newAnomaly = {
              node_id: data.node_id,
              timestamp: data.ts_ns ? parseInt(data.ts_ns) / 1000000 : Date.now(),
              anomaly_class: data.anomaly_class
            };
            return [newAnomaly, ...prev].slice(0, 5);
          });
        }
      }
    });

    // Listen for XFL round updates from server_xfl.py
    newSocket.on('xfl_update', (data) => {
      setXflRounds(prev => {
        const newRound = { ...data };
        return [...prev, newRound].slice(-20); // Keep last 20 rounds
      });
    });

    return () => newSocket.close();
  }, []);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Unified Security Dashboard</h1>
        <div className={`status-badge ${!isConnected ? 'disconnected' : ''}`}>
          <div className="status-dot"></div>
          {isConnected ? 'Connected to Backend' : 'Disconnected'}
        </div>
      </header>

      {anomalies.length > 0 && (
        <div className="alerts-container">
          {anomalies.map((a, i) => (
            <div key={i} className="alert-box active">
              <ShieldAlert className="alert-icon" size={24} />
              <div className="alert-content">
                <h4>Security Anomaly Detected</h4>
                <p>Node <strong>{a.node_id}</strong> exhibited anomalous behavior (Class: {a.anomaly_class}) at {new Date(a.timestamp).toLocaleTimeString()}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid-layout">
        <div className="glass-panel">
          <h2 className="panel-title">
            <Activity size={20} />
            Live Telemetry
          </h2>
          <MetricsChart data={metricsHistory} />
        </div>

        <div className="glass-panel">
          <h2 className="panel-title">
            <Cpu size={20} />
            Blockchain Ledger
          </h2>
          <LedgerTable transactions={transactions} />
        </div>
      </div>

      <div className="glass-panel">
        <h2 className="panel-title">
          <BrainCircuit size={20} />
          Xtreme Federated Learning — Global Model Convergence
        </h2>
        <XFLPanel rounds={xflRounds} />
      </div>
    </div>
  );
}

export default App;
