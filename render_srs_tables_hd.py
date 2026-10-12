import os
import shutil
import subprocess

PROJECT_DIR = r"d:\IoT_data_sharing"
OUT_DIR = os.path.join(PROJECT_DIR, "thesis_srs_tables_hd")
ARTIFACTS_DIR = r"C:\Users\Amith\.gemini\antigravity-ide\brain\623489b5-4130-4881-9bdc-7dac99151212"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

COMMON_STYLE = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Times New Roman", Times, Georgia, serif;
    background: #ffffff;
    color: #000000;
    width: 1000px;
    padding: 24px 30px;
    margin: 0 auto;
    display: inline-block;
  }
  .section-title {
    font-size: 16pt;
    font-weight: bold;
    margin-bottom: 12px;
    color: #000000;
  }
  .intro-text {
    font-size: 11pt;
    line-height: 1.5;
    text-align: justify;
    margin-bottom: 16px;
    color: #000000;
  }
  .table-caption {
    text-align: center;
    font-size: 12pt;
    font-weight: normal;
    margin-bottom: 10px;
    margin-top: 6px;
    color: #000000;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    border: 1.5px solid #000000;
  }
  th, td {
    border: 1.5px solid #000000;
    padding: 7px 10px;
    font-size: 11pt;
    line-height: 1.4;
    vertical-align: top;
    text-align: left;
  }
  th {
    font-weight: bold;
    background: #ffffff;
  }
  .col-req { width: 34%; font-weight: normal; }
  .col-desc { width: 66%; }
  .col-comp { width: 32%; font-weight: normal; }
  .col-spec { width: 68%; }
"""

# ─────────────────────────────────────────────────────────────
# 1. TABLE 3.1: FUNCTIONAL REQUIREMENTS
# ─────────────────────────────────────────────────────────────
t31_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Table 3.1: Functional Requirements</title><style>{COMMON_STYLE}</style></head>
<body>
  <div class="table-caption">Table 3.1: Functional Requirements</div>
  <table>
    <thead>
      <tr>
        <th class="col-req">Requirement</th>
        <th class="col-desc">Description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-req">MIoT Device Registration</td>
        <td class="col-desc">The system should allow authorized MIoT nodes or workers to participate in the distributed security framework.</td>
      </tr>
      <tr>
        <td class="col-req">Local Model Training</td>
        <td class="col-desc">Each participant worker should train the machine learning model using its own dataset without directly sharing the raw data with other workers.</td>
      </tr>
      <tr>
        <td class="col-req">Federated Model Aggregation</td>
        <td class="col-desc">The system should collect model updates from the participating workers and create an updated global model through Federated Learning.</td>
      </tr>
      <tr>
        <td class="col-req">Anomaly/Intrusion Detection</td>
        <td class="col-desc">The learning model should recognize network behaviors which are likely to be abnormal or malicious.</td>
      </tr>
      <tr>
        <td class="col-req">Secure Model Communication</td>
        <td class="col-desc">Model updates and corresponding communication should be secured by utilizing secure communication means.</td>
      </tr>
      <tr>
        <td class="col-req">Blockchain Transaction Management</td>
        <td class="col-desc">The system should log relevant security and verification transactions via the Blockchain layer.</td>
      </tr>
      <tr>
        <td class="col-req">Transaction Integrity Verification</td>
        <td class="col-desc">The system should provide tamper-resistant verification of logged blockchain transactions.</td>
      </tr>
      <tr>
        <td class="col-req">Post-Quantum Security</td>
        <td class="col-desc">The system should adopt post-quantum cryptography approaches to prevent potential quantum-based attacks.</td>
      </tr>
      <tr>
        <td class="col-req">Communication Efficiency Evaluation</td>
        <td class="col-desc">The system should monitor the performance associated with communication processes during distributed learning and data exchange.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# 2. TABLE 3.2: NON-FUNCTIONAL REQUIREMENTS
# ─────────────────────────────────────────────────────────────
t32_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Table 3.2: Non Functional Requirements</title><style>{COMMON_STYLE}</style></head>
<body>
  <div class="table-caption">Table 3.2: Non Functional Requirements</div>
  <table>
    <thead>
      <tr>
        <th class="col-req">Requirement</th>
        <th class="col-desc">Description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-req">Performance</td>
        <td class="col-desc">The system must deliver results within seconds after data submission.</td>
      </tr>
      <tr>
        <td class="col-req">Usability</td>
        <td class="col-desc">The user interface must be simple, intuitive, and accessible to non-technical users.</td>
      </tr>
      <tr>
        <td class="col-req">Scalability</td>
        <td class="col-desc">The system should handle increasing users and data with ease using cloud deployment.</td>
      </tr>
      <tr>
        <td class="col-req">Maintainability</td>
        <td class="col-desc">The system code should be modular and well-documented for easy maintenance and updates.</td>
      </tr>
      <tr>
        <td class="col-req">Security</td>
        <td class="col-desc">Ensures secure login, data encryption, and restricted access based on user roles.</td>
      </tr>
      <tr>
        <td class="col-req">Compatibility</td>
        <td class="col-desc">The system should be compatible across major browsers and devices (desktop, mobile).</td>
      </tr>
      <tr>
        <td class="col-req">Reliability</td>
        <td class="col-desc">The system should consistently produce accurate and repeatable results.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# 3. TABLE 3.3: HARDWARE REQUIREMENTS (WITH SECTION HEADER & PARAGRAPH)
# ─────────────────────────────────────────────────────────────
t33_with_text_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>3.3 Hardware Requirements</title><style>{COMMON_STYLE}</style></head>
<body>
  <div class="section-title">3.3 &nbsp; Hardware Requirements</div>
  <p class="intro-text">
    The hardware requirements outline the minimum and recommended system configurations needed to develop, train, and deploy the application. Since the project involves machine learning model training and real-time predictions through a web interface, the system must be capable of handling moderate computational tasks efficiently. Adequate memory, processing speed, and storage are necessary to ensure smooth development and testing operations.
  </p>
  <div class="table-caption">Table 3.3: Hardware Requirement Specification</div>
  <table>
    <thead>
      <tr>
        <th class="col-comp">Component</th>
        <th class="col-spec">Specification</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-comp">Processor</td>
        <td class="col-spec">Intel Core i5/i7 or AMD equivalent for smooth processing of ML tasks; ARM Cortex-A72 (Raspberry Pi 4) for edge sensing node.</td>
      </tr>
      <tr>
        <td class="col-comp">RAM</td>
        <td class="col-spec">Minimum 8GB (16GB recommended) to handle data preprocessing and model execution.</td>
      </tr>
      <tr>
        <td class="col-comp">Storage</td>
        <td class="col-spec">At least 256GB SSD (512GB recommended) for faster access to model and dataset files; 32GB MicroSD for Edge Pi.</td>
      </tr>
      <tr>
        <td class="col-comp">Display</td>
        <td class="col-spec">Standard resolution display compatible with modern web browsers.</td>
      </tr>
      <tr>
        <td class="col-comp">Network</td>
        <td class="col-spec">Stable internet connection for online access and cloud deployment.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""

# Standalone Table 3.3 only
t33_table_only_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Table 3.3: Hardware Requirement Specification</title><style>{COMMON_STYLE}</style></head>
<body>
  <div class="table-caption">Table 3.3: Hardware Requirement Specification</div>
  <table>
    <thead>
      <tr>
        <th class="col-comp">Component</th>
        <th class="col-spec">Specification</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-comp">Processor</td>
        <td class="col-spec">Intel Core i5/i7 or AMD equivalent for smooth processing of ML tasks; ARM Cortex-A72 (Raspberry Pi 4) for edge sensing node.</td>
      </tr>
      <tr>
        <td class="col-comp">RAM</td>
        <td class="col-spec">Minimum 8GB (16GB recommended) to handle data preprocessing and model execution.</td>
      </tr>
      <tr>
        <td class="col-comp">Storage</td>
        <td class="col-spec">At least 256GB SSD (512GB recommended) for faster access to model and dataset files; 32GB MicroSD for Edge Pi.</td>
      </tr>
      <tr>
        <td class="col-comp">Display</td>
        <td class="col-spec">Standard resolution display compatible with modern web browsers.</td>
      </tr>
      <tr>
        <td class="col-comp">Network</td>
        <td class="col-spec">Stable internet connection for online access and cloud deployment.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# 4. TABLE 3.4: SOFTWARE REQUIREMENTS (WITH SECTION HEADER & PARAGRAPH)
# ─────────────────────────────────────────────────────────────
t34_with_text_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>3.4 Software Requirements</title><style>{COMMON_STYLE}</style></head>
<body>
  <div class="section-title">3.4 &nbsp; Software Requirements</div>
  <p class="intro-text">
    The software requirements specify the essential tools, frameworks, and libraries used for building the application. This includes the operating system, programming language, web framework, and machine learning libraries. The project uses open-source technologies like Python, Node.js, and React, which are well-suited for developing robust, scalable, and interactive web applications integrated with machine learning models.
  </p>
  <div class="table-caption">Table 3.4: Software Requirement Specification</div>
  <table>
    <thead>
      <tr>
        <th class="col-comp">Component</th>
        <th class="col-spec">Specification</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-comp">Operating System</td>
        <td class="col-spec">Windows 10/11 or any Linux-based OS for local development; Raspberry Pi OS 64-bit for edge device.</td>
      </tr>
      <tr>
        <td class="col-comp">Frontend</td>
        <td class="col-spec">React.js, Vite, HTML5, CSS3, JavaScript, Tailwind CSS, Recharts for dynamic telemetry visualization.</td>
      </tr>
      <tr>
        <td class="col-comp">Backend Framework</td>
        <td class="col-spec">Node.js (Express.js) for REST and WebSocket APIs; Python 3.10+ (Web3.py, Pika, liboqs).</td>
      </tr>
      <tr>
        <td class="col-comp">Tools used</td>
        <td class="col-spec">Docker & Docker Compose, RabbitMQ Message Broker (TLS 1.3), Hyperledger Besu (IBFT 2.0), TensorFlow / Keras, OpenSSL, VS Code.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""

# Standalone Table 3.4 only
t34_table_only_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Table 3.4: Software Requirement Specification</title><style>{COMMON_STYLE}</style></head>
<body>
  <div class="table-caption">Table 3.4: Software Requirement Specification</div>
  <table>
    <thead>
      <tr>
        <th class="col-comp">Component</th>
        <th class="col-spec">Specification</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-comp">Operating System</td>
        <td class="col-spec">Windows 10/11 or any Linux-based OS for local development; Raspberry Pi OS 64-bit for edge device.</td>
      </tr>
      <tr>
        <td class="col-comp">Frontend</td>
        <td class="col-spec">React.js, Vite, HTML5, CSS3, JavaScript, Tailwind CSS, Recharts for dynamic telemetry visualization.</td>
      </tr>
      <tr>
        <td class="col-comp">Backend Framework</td>
        <td class="col-spec">Node.js (Express.js) for REST and WebSocket APIs; Python 3.10+ (Web3.py, Pika, liboqs).</td>
      </tr>
      <tr>
        <td class="col-comp">Tools used</td>
        <td class="col-spec">Docker & Docker Compose, RabbitMQ Message Broker (TLS 1.3), Hyperledger Besu (IBFT 2.0), TensorFlow / Keras, OpenSSL, VS Code.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""

# Definition of items to render
render_list = [
    ("Table_3_1_Functional_Requirements.html", t31_html, "Table_3_1_Functional_Requirements_UltraHD.png", 640),
    ("Table_3_2_Non_Functional_Requirements.html", t32_html, "Table_3_2_Non_Functional_Requirements_UltraHD.png", 520),
    ("Table_3_3_Hardware_Requirements_With_Text.html", t33_with_text_html, "Table_3_3_Hardware_Requirements_With_Text_UltraHD.png", 580),
    ("Table_3_3_Hardware_Requirement_Specification.html", t33_table_only_html, "Table_3_3_Hardware_Requirement_Specification_UltraHD.png", 420),
    ("Table_3_4_Software_Requirements_With_Text.html", t34_with_text_html, "Table_3_4_Software_Requirements_With_Text_UltraHD.png", 540),
    ("Table_3_4_Software_Requirement_Specification.html", t34_table_only_html, "Table_3_4_Software_Requirement_Specification_UltraHD.png", 380),
]

print("[*] Generating HTML files for Chapter 3 SRS tables...")
for hname, content, iname, height in render_list:
    hpath = os.path.join(OUT_DIR, hname)
    with open(hpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Created {hpath}")

print("\n[*] Rendering Ultra-HD 300-DPI images via Headless Edge (--force-device-scale-factor=2)...")
for hname, content, iname, height in render_list:
    hpath = os.path.join(OUT_DIR, hname)
    ipath = os.path.join(OUT_DIR, iname)
    hurl = f"file:///{hpath.replace(os.sep, '/')}"

    cmd = [
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        f"--screenshot={ipath}",
        f"--window-size=1000,{height}",
        hurl
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(ipath):
        size_kb = os.path.getsize(ipath) / 1024
        print(f"  -> Rendered Ultra-HD: {ipath} ({size_kb:.1f} KB)")
        art_path = os.path.join(ARTIFACTS_DIR, iname)
        shutil.copy2(ipath, art_path)
        print(f"     Copied to Artifacts: {art_path}")
    else:
        print(f"  ❌ Failed to render {ipath}")

print("\n[+] All Chapter 3 SRS tables generated in Ultra-HD resolution!")
