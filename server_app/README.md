# 🛡️ PQC Security Server Supervisor & Watchdog App

A native **Flutter Desktop** server supervisor and incident diagnostic application for **Windows** and **Linux**, designed to orchestrate and monitor the entire Post-Quantum IoT Telemetry, Hyperledger Besu Blockchain, and Federated Learning server infrastructure.

---

## 🌟 Key Capabilities

### 1. Sequential Master Orchestration ("Start Everything")
- **Single-Click Launch**: Boots the entire stack in dependency-aware order without spawning unmanaged terminal windows:
  1. **Docker Infrastructure**: Launches RabbitMQ, Besu, Grafana, and Alethio.
  2. **Health Gate**: Probes ports `5671` (RabbitMQ TLS) and `8545` (Besu JSON-RPC) until accepting connections.
  3. **Dashboard Backend**: Spawns `node server.js` on port `4000`.
  4. **Federated Learning Server**: Launches `server_xfl.py`.
  5. **PQC Consumer**: Launches `server.py` (`ML-KEM-768`, `ML-DSA-65`, and Besu ledger logging).
- **Graceful Tree-Kill Shutdown**: Cleanly terminates processes and child processes using `taskkill /T /F` (Windows) and POSIX process group signals (Linux).
- **Individual Service Controls**: Start, stop, or restart any single service independently without disturbing the rest of the stack.

### 2. Real-Time Watchdog & Health Matrix ("Monitor Them")
- **Instant Zero-Latency Crash Detection**: Subscribes directly to `Process.exitCode`. If a worker dies or encounters an unhandled exception, it flags the service immediately.
- **Microsecond Port Probes**: Non-blocking TCP socket pings checking ports `5671`, `5672`, `15672`, `8545`, `8080`, `4000`, and `3000`.
- **Latency & Uptime**: Real-time measurement of port connection latency in milliseconds and individual process uptime counters.
- **Web UI Launchers**: One-click in-app buttons to open RabbitMQ Web Console (`:15672`), Alethio Block Explorer (`:8080`), and Grafana (`:3000`) directly in your default browser.

### 3. Incident Diagnostics & Live Streaming Terminal ("Report Any Issues")
- **Automatic Incident Classification**: Detects crashes, exit codes != 0, and port timeouts.
- **Traceback Inspector**: Displays the exact error traceback with an **"Attempt Restart"** quick-recovery button.
- **Unified Log Stream**: Real-time aggregation of `stdout` and `stderr` across all services.
- **Filter & Search**:
  - Filter tabs: `[ALL]`, `[RabbitMQ]`, `[Besu]`, `[Backend]`, `[Consumer]`, `[XFL]`, `[Grafana]`.
  - Toggle `[Errors Only]` to instantly isolate stacktraces and warnings.
  - Text search filter.
- **Diagnostic Bundle Export**: One-click export button saving formatted diagnostic logs (`server_diagnostic_YYYYMMDD_HHMMSS.log`).

### 4. Preflight Environment Guard & Auto-Repair
- Audits system prerequisites:
  - Docker Engine connectivity (`docker info`)
  - Node.js & `dashboard-backend/node_modules`
  - Python virtual environment (`./venv`)
  - TLS certificates and PQC keys in `certs/`
  - Blockchain smart contract deployment artifacts
- In-app **"Run npm install"** repair button to automatically install missing dashboard dependencies.

---

## 🚀 Running the App

### On Windows Desktop:
```bash
cd server_app
flutter run -d windows
```

### On Linux Desktop:
```bash
cd server_app
flutter run -d linux
```

### Running Automated Tests:
```bash
cd server_app
flutter test
```
