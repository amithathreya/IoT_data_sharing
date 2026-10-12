# CHAPTER 3: SYSTEM REQUIREMENT SPECIFICATION (SRS)

## 3.1 Functional Requirements

The functional requirements define the explicit behavioral capabilities, services, data transformation workflows, and execution pipelines that the system must provide. In the context of the "Secure IoT Data Sharing with Post-Quantum Cryptography, Blockchain, and Federated Learning" framework, the functional specifications encompass multi-tier interactions spanning resource-constrained edge sensing platforms, an asynchronous message broker, a distributed private blockchain ledger, an edge-centric federated anomaly detection pipeline, and a full-stack real-time monitoring web dashboard.

### 1. Multi-Modal Sensor Data Acquisition and Hardware Abstraction (FR-1)
The system shall continuously collect telemetry from heterogeneous environmental and physical intrusion sensors deployed on edge computing nodes (Raspberry Pi). The sensing module shall interface with the DHT11 digital sensor via the Linux Industrial I/O (IIO) kernel overlay (`/sys/bus/iio/devices/iio:device0/`) to retrieve ambient temperature (in degrees Celsius) and relative humidity (in percentage) at a calibrated sampling cadence of 2.5 seconds. Concurrently, the module shall sample digital state inputs via the `gpiozero` peripheral abstraction layer for an Infrared (IR) optical break-beam sensor mapped to GPIO pin 23 and a Passive Infrared (PIR) motion sensor mapped to GPIO pin 24. To guarantee resilience in development, simulation, and hardware-disconnected modes, the acquisition driver must incorporate an automated hardware fallback mechanism that detects detached peripherals, catches input/output exceptions, and transparently substitutes synthesized, mathematically bounded baseline telemetry without interrupting the operational lifecycle of the edge node.

### 2. Post-Quantum Cryptographic (PQC) Key Establishment and Authenticated Encryption (FR-2)
To safeguard telemetry against both classical cryptanalytic attacks and future quantum computing threats (specifically Shor's algorithm for discrete logarithms and Grover's algorithm for brute-force key search), the system shall enforce a quantum-resistant cryptographic envelope on every transmitted data frame:
- **Quantum-Safe Key Encapsulation (ML-KEM-768):** The edge publisher shall utilize the NIST FIPS 203 standardized Module-Lattice-Based Key Encapsulation Mechanism (ML-KEM-768, formerly Kyber-768) provided by the `liboqs` cryptographic engine. The publisher shall ingest the server's serialized 1,184-byte public KEM key, execute encapsulation (`encap_secret`), and derive a 1,088-byte ciphertext alongside a 32-byte (256-bit) symmetric shared secret.
- **Symmetric Authenticated Payload Encryption (AES-256-GCM):** The publisher shall employ the derived 256-bit shared secret to encrypt the canonical JSON telemetry payload using Advanced Encryption Standard in Galois/Counter Mode (AES-256-GCM) with an operating-system-generated, cryptographically secure 96-bit initialization nonce (`os.urandom(12)`). This ensures full confidentiality and authenticates the payload with a 128-bit authentication tag.
- **Quantum-Safe Digital Signatures (ML-DSA-65):** The edge node shall implement NIST FIPS 204 standardized Module-Lattice-Based Digital Signature Algorithm (ML-DSA-65, formerly Dilithium3). The publisher shall compute a cryptographic signature across the concatenated authentication buffer consisting of the KEM ciphertext, the initialization nonce, and the AES ciphertext (`auth_data = kem_cipher + nonce + enc_payload`). The resulting 3,309-byte signature and the corresponding 1,952-byte public verification key shall be embedded directly within the published transport envelope.
- **Consumer Decapsulation and Zero-Trust Verification:** Upon receiving the envelope, the consumer server must strictly verify the ML-DSA-65 signature before undertaking any cryptographic decapsulation. If signature verification fails, the packet must be dropped immediately via an AMQP negative acknowledgment (`basic_nack`), preventing unauthenticated or tampered data from consuming downstream computing resources or polluting the immutable ledger. Valid packets shall have their shared secret decapsulated using the server's private KEM key (`consumer_kem_priv.key`), and the ciphertext shall be authenticated and decrypted into plaintext JSON.

### 3. Secure Transport Layer and Asynchronous Message Brokering (FR-3)
The system shall utilize an enterprise-grade RabbitMQ message broker communicating over the Advanced Message Queuing Protocol (AMQP 0-9-1) secured by mutual Transport Layer Security (TLS 1.3 mTLS) on port 5671. The transport layer shall require mutual cryptographic authentication using X.509 certificates: the client must present a valid `server_certificate.pem` signed by the private Certificate Authority (`ca_certificate.pem`), and the broker must authenticate itself to the client. The communication pipeline shall establish dedicated durable fanout exchanges—namely `sensors` for environmental telemetry, `audio_stream` for surveillance media, `fl_updates` for federated client weight uploads, and `fl_global` for global model broadcasts. The messaging subsystem must handle network drops gracefully by employing automatic channel recovery, heartbeat maintenance, and persistent message queues with delivery acknowledgments (`basic_ack`).

### 4. Smart Contract Execution and Blockchain Immutability Logging (FR-4)
The backend consumer system shall interface with an enterprise private permissioned Ethereum Virtual Machine (EVM) blockchain network powered by Hyperledger Besu running the Istanbul Byzantine Fault Tolerance 2.0 (IBFT 2.0) consensus protocol across four validator nodes. Upon successful decryption of an inbound telemetry packet:
- The system shall sort the dictionary keys canonically and compute a deterministic 256-bit cryptographic digest using the Secure Hash Algorithm (`hashlib.sha256`).
- The consumer shall construct and locally sign an EVM transaction calling the `recordTelemetry(string memory _nodeId, uint256 _timestamp, bytes32 _payloadHash)` function within the deployed `TelemetryRegistry.sol` smart contract using the node's private Ethereum account key (`BESU_PRIVATE_KEY`).
- The transaction shall be broadcasted via JSON-RPC over HTTP (`http://127.0.0.1:8545`) to the local validator node, which proposes and commits the transaction into an immutable block within an average confirmation window of less than 2.0 seconds.
- The contract shall maintain an internal array mapping (`nodeRecords[_nodeId]`), increment an atomic `totalRecords` counter, and emit an indexed `TelemetryRecorded` log event to allow external audit tools and block explorers to verify the integrity and non-repudiation of every historical sensor record.

### 5. Edge-Centric Anomaly Detection and Cyber Attack Threat Mitigation (FR-5)
The edge IoT device shall execute on-device neural network inference to detect anomalous behavior and local cyber threats without relying on continuous cloud connectivity:
- The edge node shall instantiate an undercomplete Autoencoder neural network built with TensorFlow/Keras comprising an input dimension of 20, an encoding layer of 16 neurons with ReLU activation, a bottleneck latent layer of 8 neurons, a decoding layer of 16 neurons, and an output reconstruction layer of 20 neurons compiled with Mean Squared Error (MSE) loss.
- A background monitoring daemon (`NetworkMonitor`) shall continuously poll operating system network interface statistics using `psutil.net_io_counters()` every 2.5 seconds, calculating delta bytes sent and delta bytes received scaled logarithmically via $\frac{\ln(1 + \Delta \text{bytes})}{10.0}$.
- A rolling temporal buffer of 20 scaled readings (representing 10 sequential sent/received pairs) shall be fed into the Autoencoder to calculate reconstruction loss: $\mathcal{L}_{\text{MSE}} = \frac{1}{20} \sum_{i=1}^{20} (x_i - \hat{x}_i)^2$.
- The anomaly scoring module shall compare the reconstruction loss against a dynamically calibrated threshold ($\theta_{\text{dynamic}}$). If $\mathcal{L}_{\text{MSE}} \ge \theta_{\text{dynamic}}$, the node shall flag the sample as a security breach (`anomaly_flag = 1`), log an immediate terminal alert (`[!] NETWORK ANOMALY FLAGGED`), and forward the anomaly classification indicator to the backend server and operator dashboard. This mechanism must detect high-throughput distributed denial-of-service (DDoS) and UDP flood attacks (such as those generated by `udp_flood_attack.py`) within 5 seconds of inception.

### 6. Xtreme Federated Learning (XFL) Adaptive Parameter Optimization (FR-6)
The distributed learning architecture shall facilitate collaborative anomaly detection model training across edge IoT nodes without requiring raw telemetry or local network traffic logs to leave the device boundary:
- The edge client (`client_xfl.py`) shall train the local autoencoder on local network traffic sequences collected during operation.
- **Adaptive Loss-Gating:** To minimize bandwidth consumption across constrained wireless IoT links, the client shall evaluate the local model improvement after training. Model weight updates shall only be serialized and published to the federated exchange if the local validation loss delta exceeds a predefined efficiency threshold, suppressing redundant transmissions for stabilized models.
- **PQC-Secured Weight Transmission:** Model weights shall be serialized via Pickle and Base64, bundled into an update message, digitally signed using the client's ML-DSA-65 private key, and published to the RabbitMQ `fl_updates` exchange over TLS 1.3.
- **Server Aggregation (FedAvg):** The central federated aggregation server (`server_xfl.py`) shall verify the client's quantum-safe digital signature, unpack the client weight tensors, perform weighted Federated Averaging (FedAvg), increment the global round counter, sign the aggregated weights, and broadcast the updated global model to the `fl_global` exchange.
- **Dynamic Threshold Synchronization & Hot-Reload:** Upon completing an aggregation cycle, the client shall calculate a new 3-sigma dynamic threshold ($\theta_{\text{dynamic}} = \mu_{\text{loss}} + 3\sigma_{\text{loss}}$) and write it to `local_model_threshold.json`. The edge publisher process must monitor file modification timestamps (`os.path.getmtime`) and automatically hot-reload the updated model weights and dynamic threshold into memory within 2.5 seconds without restarting the data publishing service.

### 7. Multi-Modal Audio Surveillance Streaming and Real-Time Web Dashboard (FR-7)
The system shall provide comprehensive visual and auditory monitoring capabilities for human operators:
- **Audio Surveillance Ingestion:** When an audio capture file (e.g., WAV or MP3 recording) is deposited into the edge node's `audio_out/` directory, the publisher shall encode the binary audio into Base64 format, package it alongside the telemetry envelope, publish it across the secure PQC pipeline, and purge the local file. The consumer server shall decode the binary payload, save an archival copy under `audio_in/<node_id>/<timestamp>_<filename>`, and stream the audio payload via REST to `/api/audio_stream`.
- **Operator Web Dashboard:** The system shall deliver a web dashboard powered by Express and Socket.IO on the backend and React/Vite on the frontend. The dashboard must maintain real-time bidirectional WebSocket synchronization to render dynamic rolling time-series charts of temperature and humidity, digital status indicators for PIR motion and IR beam breaks, an interactive blockchain transaction ledger displaying mined block hashes and canonical payload digests, instant visual threat banners during active network anomalies, and an embedded HTML5 audio player for acoustic surveillance.

---

## 3.2 Non-Functional Requirements

Non-functional requirements specify the operational quality attributes, architectural constraints, security benchmarks, performance criteria, and maintainability standards that the system must satisfy.

### 1. Security, Cryptographic Resilience, and Zero-Trust Compliance (NFR-1)
- **Quantum-Resistance (Post-Quantum Readiness):** The cryptographic framework must guarantee mathematical security against future cryptanalytic attacks mounted by quantum computers capable of running Shor's and Grover's algorithms. All asymmetric key encapsulation mechanisms must strictly conform to NIST FIPS 203 (ML-KEM-768, providing NIST Security Category 3 equivalence to AES-192), and all digital signature generation must conform to NIST FIPS 204 (ML-DSA-65, providing Category 3 security). This mitigates the critical Harvest-Now-Decrypt-Later (HNDL) adversary threat.
- **Transport Security:** All communication traversing the edge nodes, message broker, backend server, and web endpoints must be encrypted in transit using TLS 1.3 with mandatory mutual authentication (mTLS) utilizing ephemeral Diffie-Hellman key exchanges (`TLS_AES_256_GCM_SHA384`), disabling insecure legacy protocols (SSL v2/v3, TLS 1.0, 1.1, and 1.2).
- **Zero-Trust Policy:** The backend server and smart contract interfaces must treat all inbound data as untrusted. No message shall be parsed, processed, or logged into the blockchain ledger unless its cryptographic signature is verified against the sender's public key on the initial pass.
- **Anti-Replay and Tag Authentication:** Every telemetry transmission must incorporate a cryptographically unique 96-bit initialization nonce and a 128-bit Galois authentication tag, guaranteeing that replay attacks, bit-flipping attacks, and out-of-order packet injections are immediately detected and rejected.

### 2. Latency, Throughput, and Computational Performance (NFR-2)
- **End-to-End Pipeline Latency:** The end-to-end latency—defined as the total elapsed duration from the physical sampling of sensor data on the Raspberry Pi, through PQC encapsulation, AMQP broker routing, consumer signature verification, decryption, canonical hashing, Hyperledger Besu transaction mining, and Socket.IO broadcast to browser rendering—must not exceed 2.5 seconds under steady-state operating conditions (empirically measured at 1.82 seconds mean latency).
- **Cryptographic Overhead on Constrained Hardware:** On ARM Cortex-A72 / Cortex-A76 quad-core edge processors, the computational latency for ML-KEM-768 encapsulation must remain below 0.50 milliseconds, and ML-DSA-65 digital signature generation must complete in less than 1.00 millisecond, ensuring minimal CPU cycle consumption and preserving power on battery-backed IoT deployments.
- **Consensus Transaction Throughput:** The Hyperledger Besu private network configured with 4 IBFT 2.0 validator nodes must sustain a minimum transaction processing capacity of 50 transactions per second (TPS) with deterministic block finality achieved in under 2.0 seconds per block, completely avoiding proof-of-work mining delays or probabilistic fork reorganizations.
- **Edge Inference Throughput:** Neural network Autoencoder inference on edge network I/O buffers must execute within 5.0 milliseconds per sample, allowing continuous background anomaly monitoring without starving concurrent sensor acquisition or AMQP communication threads.

### 3. Scalability and Distributed Architectural Extensibility (NFR-3)
- **Horizontal Scalability:** The system architecture must decouple sensing, messaging, consensus, and visualization into modular microservices. The RabbitMQ broker and Hyperledger Besu blockchain network must support horizontal scaling, allowing additional IoT publisher nodes to be onboarded by simply provisioning new X.509 client certificates and distributing the server's public ML-KEM key without altering backend application code.
- **Bandwidth Conservation via Federated Learning:** The Xtreme Federated Learning (XFL) pipeline must reduce communication overhead by at least 30% compared to classical Federated Averaging (FedAvg). By employing adaptive loss-gating, nodes skip redundant model broadcasts during periods of behavioral stability, conserving wireless bandwidth across bandwidth-constrained field environments (empirically validated at 38.4% bandwidth reduction).
- **Memory Footprint Optimization:** The consumer server and edge scripts must maintain an operational resident memory footprint below 250 MB on edge nodes and below 1.5 GB on the host server, preventing memory fragmentation and resource exhaustion during continuous long-term execution.

### 4. Reliability, Fault Tolerance, and Self-Healing (NFR-4)
- **High Availability & Network Partition Recovery:** The edge publisher and backend consumer services must implement automated reconnection mechanisms incorporating exponential backoff and connection retry loops. In the event of a sudden RabbitMQ broker termination or transient network partition, neither service shall crash or terminate; upon broker restoration, both services must automatically re-negotiate mutual TLS 1.3 handshakes, re-declare required exchanges and queues, and resume telemetry streaming without manual operator intervention.
- **Byzantine Fault Tolerance:** The blockchain consensus layer must tolerate up to $F = \lfloor \frac{N - 1}{3} \rfloor$ Byzantine validator node failures or malicious actors within an $N$-node cluster. In a 4-validator network, the system must maintain unbroken ledger integrity, block production, and consensus consistency even if one validator node crashes, undergoes network disconnection, or proposes invalid blocks.
- **Hardware Disconnect Resilience:** If physical DHT11, IR, or PIR sensors experience hardware disconnection, pin degradation, or kernel driver latency, the edge sensing software must trap exceptions cleanly and transition into simulated fallback mode, continuing to broadcast synthetically generated baseline packets rather than crashing the system.

### 5. Immutability, Auditability, and Forensic Non-Repudiation (NFR-5)
- **Immutable Provenance:** Telemetry digests committed to the Hyperledger Besu smart contract must be tamper-proof and mathematically immutable. Once a block is sealed by IBFT 2.0 consensus, no historical record, sensor value, or timestamp can be modified, deleted, or backdated by any entity, including network administrators.
- **Cryptographic Auditability:** The system must support retrospective forensic auditing via standalone verification tools (`auditor.py`). Given any raw historical telemetry record extracted from database or visualization caches, the auditor tool must recompute the canonical SHA-256 digest and scan smart contract `TelemetryRecorded` event logs across all historical blocks. If a single bit in the temperature, humidity, node identifier, or timestamp was manipulated retrospectively, the system must immediately detect the mismatch and flag the record as compromised.

### 6. Usability, Maintainability, and Portability (NFR-6)
- **Intuitive Web Visualization:** The web dashboard must provide an intuitive, responsive user experience suitable for tactical operations centers, featuring dark-mode aesthetic styling, color-coded status badges, real-time Recharts time-series graphs, and interactive tabular views with copyable cryptographic hashes.
- **Decoupled Codebase & Configuration Management:** All configuration parameters—such as broker host addresses, ports, private keys, contract addresses, and API endpoints—must be segregated into external environment configuration files (`.env`) rather than hardcoded in application source files.
- **Automated Bootstrap:** The multi-tier system must support streamlined local execution via automated startup scripts (`start_all.ps1`) that orchestrate Docker containers, the Express backend, the React frontend, the federated learning server, and the AMQP consumer in independent concurrent execution threads.

---

## 3.3 Hardware Requirements

The hardware requirements delineate the physical computing machinery, processor architectures, memory capacities, peripheral sensors, and network interfaces essential to deploy the edge sensing platform, central blockchain infrastructure, message broker, and administrative monitoring stations.

### 1. Edge Sensing and Edge-AI Computing Node (Raspberry Pi 4 / 5)
The edge sensing tier is designed to operate on single-board computer (SBC) architectures capable of executing Python 3 runtime environments, hardware GPIO interfacing, lightweight deep neural network inference, and post-quantum cryptographic computations:
- **Central Processing Unit (SoC):** Broadcom BCM2711, Quad-core ARM Cortex-A72 (ARM v8) 64-bit SoC operating at a base clock frequency of 1.5 GHz (or Broadcom BCM2712 Quad-core Cortex-A76 @ 2.4 GHz for Raspberry Pi 5). The processor must support ARM Neon SIMD vector instructions to accelerate lattice-based post-quantum cryptographic operations in `liboqs`.
- **System Memory (RAM):** Minimum 4 GB LPDDR4-3200 SDRAM (8 GB recommended) to accommodate concurrent execution of the Python runtime, TensorFlow runtime libraries, `liboqs` cryptographic shared libraries, and rolling network traffic sampling buffers.
- **Primary Storage:** Minimum 32 GB Class 10 High-Endurance MicroSD card (UHS-I U3 / V30 specification) providing sustained sequential read throughput $\ge 90\text{ MB/s}$ and write throughput $\ge 30\text{ MB/s}$ for reliable OS boot, model weight persistence, and temporary buffer caching.
- **Environmental Sensing Hardware (DHT11):** Digital relative humidity and temperature sensor module operating over a 3.3V to 5.0V DC input range. Temperature measurement range: 0°C to 50°C with $\pm 2.0\text{°C}$ accuracy; Humidity measurement range: 20% to 90% RH with $\pm 5.0\%\text{ RH}$ accuracy; single-wire bidirectional digital protocol interfaced directly with the Raspberry Pi GPIO pin via the Linux Industrial I/O kernel overlay.
- **Optical Intrusion Sensor (IR Obstacle / Beam Break):** Active infrared sensor module featuring an IR transmitter LED, photodiode receiver, and LM393 comparator circuitry. Operating voltage: 3.3V DC; effective detection range: 2 cm to 30 cm; digital output pin connected to Raspberry Pi Physical Pin 16 (BCM GPIO 23).
- **Human Motion Sensor (PIR HC-SR501):** Pyroelectric passive infrared motion sensor operating on 5.0V DC power with a 3.3V logic level output. Detection range: 3 to 7 meters over a 120-degree cone; digital trigger output connected to Raspberry Pi Physical Pin 18 (BCM GPIO 24).
- **Surveillance Audio Capture Device:** Standard USB Omnidirectional Electret Condenser Microphone supporting 16-bit PCM digital audio capture at 16 kHz to 44.1 kHz sampling rates over USB 2.0 interface.
- **Power Delivery Unit:** Official Raspberry Pi USB-C Power Supply delivering regulated 5.1V DC at 3.0A (15.3 Watts) to prevent undervoltage throttling during intensive cryptographic handshakes.
- **Networking Hardware:** Integrated dual-band 2.4 GHz / 5.0 GHz IEEE 802.11ac Wi-Fi module or onboard Gigabit Ethernet (1000BASE-T) port connected to the local network infrastructure.

### 2. Central Server, Message Broker, and Blockchain Host Machine
The host machine executes the multi-node Hyperledger Besu blockchain network, the RabbitMQ message broker container, the federated aggregation engine, the consumer backend, and the web streaming server:
- **Processor:** Intel Core i7 (10th Gen or later) or AMD Ryzen 7 / Ryzen 9 processor featuring a minimum of 8 physical cores and 16 execution threads, with a base clock frequency $\ge 2.8\text{ GHz}$ and boost frequency $\ge 4.5\text{ GHz}$. The CPU must support Advanced Vector Extensions 2 (AVX2), AES-NI hardware acceleration, and hardware virtualization (Intel VT-x / AMD-V) for Docker container execution.
- **System Memory (RAM):** Minimum 16 GB DDR4/DDR5 SDRAM operating at $\ge 3200\text{ MHz}$ (32 GB recommended). This memory pool is partitioned to sustain four concurrent Hyperledger Besu validator nodes (allocating $\approx 1.5\text{ GB}$ JVM heap per node), the Erlang-based RabbitMQ broker ($\approx 1\text{ GB}$), the Node.js Express backend, and the Python consumer service.
- **Primary Storage (Solid State Drive):** Minimum 512 GB NVMe M.2 Solid State Drive (PCIe Gen 3.0 x4 or PCIe Gen 4.0 x4) providing sequential read throughput $\ge 3,000\text{ MB/s}$ and random write throughput $\ge 200,000\text{ IOPS}$. High I/O throughput is mandatory to handle concurrent block read/write operations across four independent validator instances running RocksDB backends.
- **Network Interface Card (NIC):** Integrated 10/100/1000 Mbps Gigabit Ethernet controller (RJ-45) connected to an isolated gigabit network switch or dedicated local wireless router.

### 3. Cyber Attack Simulation Host (Adversary Workstation)
A secondary workstation connected to the same private subnet is required to simulate distributed denial-of-service and network flood cyber-attacks against the edge IoT node:
- **Processor:** Intel Core i5 / AMD Ryzen 5 quad-core processor ($\ge 2.4\text{ GHz}$).
- **System Memory:** Minimum 8 GB RAM.
- **Network Interface:** 1000BASE-T Gigabit Ethernet or 802.11ac Wi-Fi interface capable of generating sustained packet bursts exceeding 50,000 packets per second (using `udp_flood_attack.py`).

---

## 3.4 Software Requirements

The software requirements specify the operating system distributions, container runtime engines, programming language interpreters, cryptographic development kits, blockchain implementations, machine learning frameworks, and web development stacks necessary to construct and maintain the system.

### 1. Operating Systems and System Environments
- **Edge Computing Nodes:** Raspberry Pi OS 64-bit (Debian 12 'Bookworm') running Linux kernel version 6.1 or later. The OS must have the Linux Industrial I/O (IIO) subsystem active and the standard `gpiozero` and `libgpiod` libraries installed for low-latency peripheral access.
- **Central Server Host:** Microsoft Windows 11 Professional 64-bit (Build 22621 or higher) or Ubuntu Linux 22.04 LTS (Jammy Jellyfish). The host must have Windows Subsystem for Linux 2 (WSL 2) enabled, PowerShell 7.0+ installed, and Docker Desktop configured with the Linux container backend.
- **Adversary Node:** Any POSIX-compliant Linux distribution (Ubuntu, Debian, Fedora) or Windows 10/11 running Python 3.10+.

### 2. Containerization and Messaging Infrastructure
- **Container Engine:** Docker Engine Community Edition version 24.0 or higher with Docker Compose version 2.20+.
- **Message Broker:** RabbitMQ version 3.12 or higher running inside an official Alpine-based Docker container. The broker must be configured with the native Erlang/OTP 26 runtime and configured with an SSL/TLS listener on port 5671 enforcing TLS 1.3, mutual certificate verification (`verify_peer`), fail-if-no-peer-cert (`true`), and TLS cipher suites `TLS_AES_256_GCM_SHA384` and `TLS_CHACHA20_POLY1305_SHA256`.
- **AMQP Client Library:** Python `pika` library version 1.3.2+ providing blocking connection interfaces, SSL options integration, fanout exchange declarations, and delivery tag acknowledgments.

### 3. Cryptographic Frameworks and Toolkits
- **Post-Quantum Cryptography Engine:** Open Quantum Safe (`liboqs`) C library version 0.10.0+ compiled with hardware optimization flags, paired with the official Python wrapper `liboqs-python` version 0.16.0.1. The engine provides implementations for:
  - NIST FIPS 203: Module-Lattice-Based Key Encapsulation Mechanism (`ML-KEM-768`).
  - NIST FIPS 204: Module-Lattice-Based Digital Signature Algorithm (`ML-DSA-65`).
- **Classical Cryptography Toolkit:** Python `cryptography` package version 42.0+ (utilizing the OpenSSL 3.0+ backend) providing authenticated symmetric encryption primitives (`AESGCM` with 256-bit keys and 96-bit nonces) and X.509 certificate parsing.
- **Certificate Authority Tools:** OpenSSL version 3.0.2+ command-line utility used to generate RSA-4096 / ECDSA P-256 certificate authority roots (`ca_certificate.pem`), server certificates (`server_certificate.pem`), and private signing keys (`server_key.pem`).

### 4. Blockchain Consensus Engine and EVM Toolchain
- **Blockchain Client:** Hyperledger Besu version 23.4+ enterprise Ethereum client executed on Java Virtual Machine (OpenJDK 17 / 21 LTS). The network is configured with a 4-node private consortium running Istanbul Byzantine Fault Tolerance 2.0 (IBFT 2.0) consensus with a fixed block time of 2 seconds and zero gas price requirements (`min-gas-price = 0`).
- **Smart Contract Language:** Solidity version 0.8.20 (`pragma solidity ^0.8.0`) utilized to author the `TelemetryRegistry.sol` smart contract with structured record mappings, atomic counters, and event emissions.
- **Smart Contract Compilation & Deployment:** Python `py-solc-x` version 2.0.2+ and Web3.py deployment scripts (`deploy.py`) utilizing Ethereum JSON-RPC 2.0 APIs over HTTPProvider (`http://127.0.0.1:8545`).
- **Web3 Interface Engine:** Python `web3.py` library version 6.15+ (or version 8.0.0+) supporting transaction construction, offline private key signing (`eth_account`), transaction broadcasting (`send_raw_transaction`), receipt polling, and event filter monitoring (`TelemetryRecorded.create_filter`).

### 5. Machine Learning and Edge Analytics Stack
- **Deep Learning Framework:** TensorFlow version 2.16+ (or TensorFlow Lite runtime) compiled for 64-bit ARM and x86_64 architectures with Keras deep learning API. Inter-op and intra-op thread counts are tuned (`tf.config.threading.set_intra_op_parallelism_threads(1)`) to avoid CPU resource starvation on the Raspberry Pi.
- **Mathematical Preprocessing:** NumPy version 1.26+ (or version 2.5+) and Pandas version 2.2+ for multidimensional array manipulation, log-scaling transformations, and temporal sliding window construction.
- **System Monitoring Toolkit:** Python `psutil` library version 5.9+ for sampling kernel network I/O counter bytes sent and received.

### 6. Full-Stack Web Application and Visualization Framework
- **Backend Runtime Environment:** Node.js version 20.x LTS (Iron) with the npm package manager version 10.x.
- **Backend Server Framework:** Express.js version 4.19+ configured with CORS middleware and JSON body parser with 50 MB payload limits to support high-resolution base64 surveillance audio packets.
- **Real-Time Communication Protocol:** Socket.IO server version 4.7+ (Node.js) paired with Socket.IO client version 4.7+ (React) enabling real-time WebSocket event emission (`metrics_update`, `xfl_update`, `live_audio_stream`).
- **Frontend Framework:** React 18 single-page application bundled with Vite 5.x build tooling.
- **Visualization and Styling Components:**
  - Tailwind CSS / Vanilla CSS3 design system with dark-mode aesthetic styling.
  - Recharts charting library version 2.12+ for responsive SVG-based time-series telemetry rendering.
  - Lucide React icon library version 0.359+ for telemetry status iconography.
  - HTML5 native Audio API for immediate browser-based playback of decoded surveillance audio streams.
