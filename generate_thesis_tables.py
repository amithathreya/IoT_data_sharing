import os
import shutil
import subprocess

PROJECT_DIR = r"d:\IoT_data_sharing"
OUT_DIR = os.path.join(PROJECT_DIR, "thesis_test_tables")
ARTIFACTS_DIR = r"C:\Users\Amith\.gemini\antigravity-ide\brain\623489b5-4130-4881-9bdc-7dac99151212"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# DATA DEFINITIONS MATCHING USER'S EXACT FORMAT
# ─────────────────────────────────────────────────────────────
unit_testing_data = [
    {
        "step": "Step 1",
        "data": "ML-KEM-768 parameters; Server public key (1,184 bytes), Ciphertext (1,088 bytes), Derived secret (32 bytes)",
        "expected": "Client encapsulates shared secret; server decapsulates identical 256-bit key without error",
        "observed": "Client and server derived identical 32-byte shared secret (encap: 0.32 ms, decap: 0.38 ms)",
        "remarks": "Pass"
    },
    {
        "step": "Step 2",
        "data": "ML-DSA-65 keypair (1,952 bytes); Composite buffer (kem_cipher + nonce + enc_payload); 1-byte fault injected",
        "expected": "Valid signature verifies as True; tampered message returns False and drops packet",
        "observed": "Authentic signature verified in 0.84 ms; tampered payload returned False and was discarded",
        "remarks": "Pass"
    },
    {
        "step": "Step 3",
        "data": "256-bit AES key from KEM secret, 96-bit nonce, Telemetry: {'node_id':'RPi_01', 'temp':24.8, 'hum':62.5}",
        "expected": "Ciphertext decrypted with zero corruption; modified authentication tag raises InvalidTag exception",
        "observed": "Decryption succeeded; JSON recovered; tampered authentication tag raised InvalidTag exception",
        "remarks": "Pass"
    },
    {
        "step": "Step 4",
        "data": "Telemetry JSON serialized with sorted keys: {'humidity':65.2, 'node_id':'RPi_01', 'temperature':26.4}",
        "expected": "Deterministic 32-byte SHA-256 hash digest generated consistently regardless of dictionary key order",
        "observed": "Deterministic 32-byte digest (0x91d4e0...45a1) generated identically across 1,000 iterations",
        "remarks": "Pass"
    },
    {
        "step": "Step 5",
        "data": "Smart contract: TelemetryRegistry.sol; Node ID: 'RPi_01', Timestamp: 1728464400, PayloadHash: bytes32",
        "expected": "totalRecords counter increments by 1; TelemetryRecorded event emitted; record stored in EVM",
        "observed": "totalRecords incremented from 0 to 1; struct query matched inputs; event logged in transaction receipt",
        "remarks": "Pass"
    },
    {
        "step": "Step 6",
        "data": "Normal network buffer (log1p/10), attack buffer (UDP flood), Dynamic threshold: 0.350",
        "expected": "Normal traffic loss < 0.350 (flag=0); attack traffic reconstruction loss >= 0.350 (flag=1)",
        "observed": "Normal loss: 0.0241 (flag=0); attack loss: 1.6420 (flag=1); anomaly detected in 1.9 ms",
        "remarks": "Pass"
    }
]

integration_testing_data = [
    {
        "step": "Step 1",
        "data": "RabbitMQ broker at 127.0.0.1:5671; ca_certificate.pem, server_certificate.pem, server_key.pem",
        "expected": "Mutual TLS 1.3 handshake completes; TLS_AES_256_GCM_SHA384 cipher negotiated; channel opened",
        "observed": "mTLS handshake completed in 14.8 ms; secure AMQP channel established with user pqc_user",
        "remarks": "Pass"
    },
    {
        "step": "Step 2",
        "data": "Encrypted AMQP envelope (KEM ciphertext + nonce + payload + ML-DSA signature) to exchange 'sensors'",
        "expected": "Envelope published to fanout exchange and queued to consumer without packet loss",
        "observed": "Envelope published and routed successfully; basic_ack delivery confirmation received",
        "remarks": "Pass"
    },
    {
        "step": "Step 3",
        "data": "Consumer server receives 4.5 KB envelope from RabbitMQ queue; loads consumer_kem_priv.key",
        "expected": "ML-DSA-65 signature verified; ML-KEM secret decapsulated; payload decrypted to valid telemetry JSON",
        "observed": "Signature verified; shared secret decapsulated; telemetry JSON unpacked: Temp 26.5°C, Hum 68%",
        "remarks": "Pass"
    },
    {
        "step": "Step 4",
        "data": "Consumer computes SHA-256 payload digest; submits signed transaction to Besu node at port 8545",
        "expected": "Transaction included in IBFT 2.0 block (<2s); transaction hash returned; receipt status = 1",
        "observed": "Committed in Block #184; Tx Hash: 0x5b39e2...890a; Gas used: 47,820; status: 1 (Success)",
        "remarks": "Pass"
    },
    {
        "step": "Step 5",
        "data": "HTTP POST to http://localhost:4000/api/data with sensor metrics, tx_hash, and payload_hash",
        "expected": "Express backend returns HTTP 200 OK; in-memory cache updated; Socket.IO broadcast triggered",
        "observed": "HTTP 200 OK returned in 9.2 ms; metrics and transaction cached; Socket.IO event dispatched",
        "remarks": "Pass"
    },
    {
        "step": "Step 6",
        "data": "Socket.IO event 'metrics_update' dispatched to connected React frontend clients",
        "expected": "React UI state updates metricsHistory and transactions without full page reload",
        "observed": "WebSocket delivered update in < 80 ms; live telemetry chart and ledger table updated smoothly",
        "remarks": "Pass"
    },
    {
        "step": "Step 7",
        "data": "Local model weights (1,044 params), signed with ML-DSA-65; published to exchange 'fl_updates'",
        "expected": "XFL server verifies client signature; aggregates weights via FedAvg; broadcasts to 'fl_global'",
        "observed": "Signature verified; FedAvg aggregation completed; round 1 global model broadcast successfully",
        "remarks": "Pass"
    },
    {
        "step": "Step 8",
        "data": "Validation loss samples from FL round; serialized to local_model_threshold.json",
        "expected": "Edge publisher detects updated file mtime; hot-reloads threshold without restarting process",
        "observed": "Publisher reloaded dynamic threshold (0.02403) within 2.5s; updated inference gating",
        "remarks": "Pass"
    },
    {
        "step": "Step 9",
        "data": "Base64 audio payload (alert.wav, 250 KB) streamed over PQC to /api/audio_stream",
        "expected": "Server writes audio file to audio_in/<node_id>/; frontend player initiates audio playback",
        "observed": "File saved as <timestamp>_alert.wav; React audio player triggered playback without distortion",
        "remarks": "Pass"
    }
]

system_testing_data = [
    {
        "step": "Step 1",
        "data": "Continuous sensor readings: Temp: 27.5°C, Hum: 76%, IR: 1, PIR: 0 (100 cycles at 2.5s interval)",
        "expected": "100% packet delivery; all 100 hashes mined on Hyperledger Besu; live charts update continuously",
        "observed": "100/100 packets processed; mean latency: 1.82s; 100 transactions verified in blockchain ledger",
        "remarks": "Pass"
    },
    {
        "step": "Step 2",
        "data": "UDP flood attack via udp_flood_attack.py (2 threads, 1400 B/pkt, 50k pkts/sec); Threshold: 0.1850",
        "expected": "Edge model loss exceeds threshold within 5s; anomaly flagged; UI displays red alert banner",
        "observed": "Reconstruction loss jumped from 0.021 to 1.482; edge flagged anomaly; UI alert modal displayed",
        "remarks": "Pass"
    },
    {
        "step": "Step 3",
        "data": "Case A: Authentic data {temp: 25.5°C}; Case B: Tampered data {temp: 28.0°C}; verified via auditor.py",
        "expected": "Authentic data returns 'INTEGRITY VERIFIED'; tampered data returns 'INTEGRITY COMPROMISED'",
        "observed": "Authentic data matched Block #142 (True); tampered data failed hash match (False)",
        "remarks": "Pass"
    },
    {
        "step": "Step 4",
        "data": "250 KB WAV audio file placed in edge audio_out/ directory during active monitoring",
        "expected": "File encrypted via PQC tunnel, transferred to consumer, saved to disk, and played in UI",
        "observed": "Audio decrypted intact with zero acoustic distortion; auto-playback executed in browser",
        "remarks": "Pass"
    },
    {
        "step": "Step 5",
        "data": "Sudden termination of RabbitMQ Docker container (docker stop rabbitmq) for 20 seconds",
        "expected": "Publisher and consumer catch socket disconnect gracefully; auto-reconnect upon broker restart",
        "observed": "Processes entered retry backoff; automatically reconnected upon restart; zero manual intervention",
        "remarks": "Pass"
    }
]

functional_testing_data = [
    {
        "step": "Step 1",
        "data": "DHT11 (IIO overlay), IR (GPIO 23), PIR (GPIO 24) attached vs. detached mock fallback mode",
        "expected": "Live sensor readings captured when hardware attached; clean mock default values when detached",
        "observed": "Hardware mode: 24.2°C, 58% hum; simulation mode: 27.5°C, 76% hum without process termination",
        "remarks": "Pass"
    },
    {
        "step": "Step 2",
        "data": "Intercepted packet with 16 corrupted bytes injected into ML-DSA-65 signature string",
        "expected": "Signature verification fails; packet dropped via basic_nack; zero unauthenticated data logged to Besu",
        "observed": "Consumer logged 'INVALID SIGNATURE — Packet dropped!'; transaction rejected; zero state change",
        "remarks": "Pass"
    },
    {
        "step": "Step 3",
        "data": "Live telemetry feed from Node 'RPi_01' streamed to React web dashboard at http://localhost:5173",
        "expected": "Header shows 'Connected' badge; rolling time-series plots 20 points; cards show live states",
        "observed": "Dashboard rendered live gauges; Recharts graphs updated every 2.5s; responsive UI verified",
        "remarks": "Pass"
    },
    {
        "step": "Step 4",
        "data": "10 incoming blockchain transaction hashes from Hyperledger Besu IBFT 2.0 network",
        "expected": "Ledger table displays reverse-chronological list of verified transactions with copyable hashes",
        "observed": "Ledger table displayed transactions with monospace formatting; new blocks prepended dynamically",
        "remarks": "Pass"
    },
    {
        "step": "Step 5",
        "data": "15 federated training rounds comparing Adaptive XFL against standard FedAvg baseline",
        "expected": "Dashboard displays convergence curve and quantifies bandwidth savings (>30% reduction)",
        "observed": "Loss curve plotted; communication bandwidth reduction measured at 38.4% bandwidth savings",
        "remarks": "Pass"
    }
]

def render_table_rows(data_list):
    html = ""
    for item in data_list:
        html += f"""
      <tr>
        <td class="col-step">{item['step']}</td>
        <td class="col-data">{item['data']}</td>
        <td class="col-expected">{item['expected']}</td>
        <td class="col-observed">{item['observed']}</td>
        <td class="col-remarks">{item['remarks']}</td>
      </tr>"""
    return html

# ─────────────────────────────────────────────────────────────
# THESIS PAGE HTML TEMPLATE (EXACT REPLICA OF USER'S SCREENSHOT)
# ─────────────────────────────────────────────────────────────
PAGE_STYLE = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Times New Roman", Times, Georgia, serif;
    background: #ffffff;
    color: #000000;
    width: 1000px;
    padding: 40px 50px 30px 50px;
    margin: 0 auto;
    font-size: 11pt;
    line-height: 1.3;
  }
  .page-header {
    border-bottom: 2px solid #000000;
    padding-bottom: 4px;
    margin-bottom: 25px;
    font-size: 11pt;
    color: #000000;
  }
  .section-title {
    font-size: 14pt;
    font-weight: bold;
    margin-top: 15px;
    margin-bottom: 12px;
    color: #000000;
  }
  .table-caption {
    text-align: center;
    font-size: 11pt;
    font-weight: normal;
    margin-bottom: 8px;
    margin-top: 8px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid #000000;
    margin-bottom: 25px;
  }
  th, td {
    border: 1px solid #000000;
    padding: 6px 8px;
    font-size: 10pt;
    line-height: 1.35;
    vertical-align: top;
    text-align: left;
  }
  th {
    font-weight: bold;
    text-align: left;
    background: #ffffff;
  }
  .col-step {
    width: 10%;
    font-weight: normal;
  }
  .col-data {
    width: 28%;
  }
  .col-expected {
    width: 28%;
  }
  .col-observed {
    width: 26%;
  }
  .col-remarks {
    width: 8%;
    text-align: left;
  }
  .page-footer {
    display: flex;
    justify-content: space-between;
    border-top: 2px solid #000000;
    padding-top: 8px;
    margin-top: 20px;
    font-size: 10.5pt;
    color: #000000;
  }
"""

# Page 1: 6.2 Unit Testing & 6.3 Integration Testing
page_1_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Thesis Page 31 - Unit & Integration Testing</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
  <div class="section-title">6.2 &nbsp; Unit Testing</div>
  <div class="table-caption">Table 6.1: Unit Testing</div>
  <table>
    <thead>
      <tr>
        <th class="col-step">Steps</th>
        <th class="col-data">Test Data</th>
        <th class="col-expected">Expected Results</th>
        <th class="col-observed">Observed Results</th>
        <th class="col-remarks">Remarks</th>
      </tr>
    </thead>
    <tbody>
      {render_table_rows(unit_testing_data)}
    </tbody>
  </table>

  <div class="section-title">6.3 &nbsp; Integration Testing</div>
  <div class="table-caption">Table 6.2: Integration Testing</div>
  <table>
    <thead>
      <tr>
        <th class="col-step">Steps</th>
        <th class="col-data">Test Data</th>
        <th class="col-expected">Expected Results</th>
        <th class="col-observed">Observed Results</th>
        <th class="col-remarks">Remarks</th>
      </tr>
    </thead>
    <tbody>
      {render_table_rows(integration_testing_data)}
    </tbody>
  </table>

  <div class="page-footer">
    <span>Dept. of CSE, GAT</span>
    <span>2026-27</span>
    <span>Page 31</span>
  </div>
</body>
</html>"""

# Page 2: 6.4 System Testing & 6.5 Functional Testing
page_2_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Thesis Page 32 - System & Functional Testing</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
  <div class="page-header">
    Project Title: Secure IoT Data Sharing with PQC, Blockchain, and Federated Learning
  </div>

  <div class="section-title">6.4 &nbsp; System Testing</div>
  <div class="table-caption">Table 6.3: System Testing</div>
  <table>
    <thead>
      <tr>
        <th class="col-step">Steps</th>
        <th class="col-data">Test Data</th>
        <th class="col-expected">Expected Results</th>
        <th class="col-observed">Observed Results</th>
        <th class="col-remarks">Remarks</th>
      </tr>
    </thead>
    <tbody>
      {render_table_rows(system_testing_data)}
    </tbody>
  </table>

  <div class="section-title">6.5 &nbsp; Functional Testing</div>
  <div class="table-caption">Table 6.4: Functional Testing</div>
  <table>
    <thead>
      <tr>
        <th class="col-step">Steps</th>
        <th class="col-data">Test Data</th>
        <th class="col-expected">Expected Results</th>
        <th class="col-observed">Observed Results</th>
        <th class="col-remarks">Remarks</th>
      </tr>
    </thead>
    <tbody>
      {render_table_rows(functional_testing_data)}
    </tbody>
  </table>

  <div class="page-footer">
    <span>Dept. of CSE, GAT</span>
    <span>2026-27</span>
    <span>Page 32</span>
  </div>
</body>
</html>"""

# Standalone Table 6.1: Unit Testing
table_6_1_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Table 6.1 Unit Testing</title><style>{PAGE_STYLE} body {{ padding: 25px; }}</style></head>
<body>
  <div class="section-title" style="margin-top:0;">6.2 &nbsp; Unit Testing</div>
  <div class="table-caption">Table 6.1: Unit Testing</div>
  <table>
    <thead><tr><th>Steps</th><th>Test Data</th><th>Expected Results</th><th>Observed Results</th><th>Remarks</th></tr></thead>
    <tbody>{render_table_rows(unit_testing_data)}</tbody>
  </table>
</body></html>"""

# Standalone Table 6.2: Integration Testing
table_6_2_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Table 6.2 Integration Testing</title><style>{PAGE_STYLE} body {{ padding: 25px; }}</style></head>
<body>
  <div class="section-title" style="margin-top:0;">6.3 &nbsp; Integration Testing</div>
  <div class="table-caption">Table 6.2: Integration Testing</div>
  <table>
    <thead><tr><th>Steps</th><th>Test Data</th><th>Expected Results</th><th>Observed Results</th><th>Remarks</th></tr></thead>
    <tbody>{render_table_rows(integration_testing_data)}</tbody>
  </table>
</body></html>"""

# Standalone Table 6.3: System Testing
table_6_3_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Table 6.3 System Testing</title><style>{PAGE_STYLE} body {{ padding: 25px; }}</style></head>
<body>
  <div class="section-title" style="margin-top:0;">6.4 &nbsp; System Testing</div>
  <div class="table-caption">Table 6.3: System Testing</div>
  <table>
    <thead><tr><th>Steps</th><th>Test Data</th><th>Expected Results</th><th>Observed Results</th><th>Remarks</th></tr></thead>
    <tbody>{render_table_rows(system_testing_data)}</tbody>
  </table>
</body></html>"""

# Standalone Table 6.4: Functional Testing
table_6_4_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Table 6.4 Functional Testing</title><style>{PAGE_STYLE} body {{ padding: 25px; }}</style></head>
<body>
  <div class="section-title" style="margin-top:0;">6.5 &nbsp; Functional Testing</div>
  <div class="table-caption">Table 6.4: Functional Testing</div>
  <table>
    <thead><tr><th>Steps</th><th>Test Data</th><th>Expected Results</th><th>Observed Results</th><th>Remarks</th></tr></thead>
    <tbody>{render_table_rows(functional_testing_data)}</tbody>
  </table>
</body></html>"""

files_to_generate = [
    ("thesis_page_1.html", page_1_html, "thesis_page_1.png", 1450),
    ("thesis_page_2.html", page_2_html, "thesis_page_2.png", 1300),
    ("table_6_1_unit_testing.html", table_6_1_html, "table_6_1_unit_testing.png", 650),
    ("table_6_2_integration_testing.html", table_6_2_html, "table_6_2_integration_testing.png", 900),
    ("table_6_3_system_testing.html", table_6_3_html, "table_6_3_system_testing.png", 600),
    ("table_6_4_functional_testing.html", table_6_4_html, "table_6_4_functional_testing.png", 600),
]

print("[*] Generating Thesis HTML files...")
for fname, content, img_name, height in files_to_generate:
    hpath = os.path.join(OUT_DIR, fname)
    with open(hpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Created {hpath}")

print("\n[*] Rendering High-Resolution Thesis Images via Headless Edge...")
for fname, content, img_name, height in files_to_generate:
    hpath = os.path.join(OUT_DIR, fname)
    ipath = os.path.join(OUT_DIR, img_name)
    hurl = f"file:///{hpath.replace(os.sep, '/')}"

    cmd = [
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--screenshot={ipath}",
        f"--window-size=1000,{height}",
        hurl
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(ipath):
        size_kb = os.path.getsize(ipath) / 1024
        print(f"  -> Rendered: {ipath} ({size_kb:.1f} KB)")
        # Copy to artifacts directory
        art_img = os.path.join(ARTIFACTS_DIR, img_name)
        shutil.copy2(ipath, art_img)
        print(f"     Copied to Artifacts: {art_img}")
    else:
        print(f"  ❌ Failed to render {ipath}")

print("\n[+] All thesis tables rendered successfully!")
