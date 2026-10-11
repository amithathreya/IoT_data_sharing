import 'dart:io';
import 'package:path/path.dart' as p;
import '../platform/platform_adapter.dart';

class PreflightItem {
  final String id;
  final String name;
  final String description;
  final bool isSatisfied;
  final String? errorOrWarning;
  final String? fixActionLabel;
  final bool isCritical;

  PreflightItem({
    required this.id,
    required this.name,
    required this.description,
    required this.isSatisfied,
    this.errorOrWarning,
    this.fixActionLabel,
    this.isCritical = false,
  });
}

class PreflightReport {
  final List<PreflightItem> items;
  final DateTime timestamp;

  PreflightReport({
    required this.items,
    required this.timestamp,
  });

  bool get hasCriticalErrors => items.any((i) => !i.isSatisfied && i.isCritical);
  bool get hasWarnings => items.any((i) => !i.isSatisfied && !i.isCritical);
  bool get isReady => items.every((i) => i.isSatisfied);
}

class PreflightService {
  final Directory repoRoot;

  PreflightService(this.repoRoot);

  /// Audits the entire environment
  Future<PreflightReport> runAudit() async {
    final List<PreflightItem> items = [];

    // 1. Check Docker Daemon
    bool dockerOk = false;
    String? dockerError;
    try {
      final res = await Process.run('docker', ['info']);
      if (res.exitCode == 0) {
        dockerOk = true;
      } else {
        dockerError = 'Docker daemon is not running or unreachable';
      }
    } catch (e) {
      dockerError = 'Docker command not found in PATH: $e';
    }
    items.add(PreflightItem(
      id: 'docker',
      name: 'Docker Engine',
      description: 'Required for RabbitMQ, Grafana, Hyperledger Besu, and Alethio',
      isSatisfied: dockerOk,
      errorOrWarning: dockerError,
      fixActionLabel: PlatformAdapter.isWindows ? 'Launch Docker Desktop' : 'Start Docker Service',
      isCritical: true,
    ));

    // 2. Check Node.js and dashboard-backend/node_modules
    bool nodeModulesOk = false;
    String? nodeModulesError;
    final nodeModulesDir = Directory(p.join(repoRoot.path, 'dashboard-backend', 'node_modules'));
    if (nodeModulesDir.existsSync()) {
      nodeModulesOk = true;
    } else {
      nodeModulesError = 'node_modules missing in dashboard-backend (npm install required)';
    }
    items.add(PreflightItem(
      id: 'node_modules',
      name: 'Dashboard Backend Dependencies',
      description: 'Node.js packages (express, socket.io, cors) for port 4000',
      isSatisfied: nodeModulesOk,
      errorOrWarning: nodeModulesError,
      fixActionLabel: 'Run npm install',
      isCritical: true,
    ));

    // 3. Check Python venv
    bool pythonVenvOk = false;
    String? pythonError;
    final venvDir = Directory(p.join(repoRoot.path, 'venv'));
    if (venvDir.existsSync()) {
      pythonVenvOk = true;
    } else {
      pythonError = 'Python virtualenv (./venv) not found. May fallback to system Python.';
    }
    items.add(PreflightItem(
      id: 'python_venv',
      name: 'Python Environment (venv)',
      description: 'Virtual environment for PQC consumer & Federated Learning server',
      isSatisfied: pythonVenvOk,
      errorOrWarning: pythonError,
      fixActionLabel: 'Create venv',
      isCritical: false, // Can fallback to system python if packages installed
    ));

    // 4. Check Certs & PQC Keys
    bool certsOk = false;
    String? certsError;
    final caCert = File(p.join(repoRoot.path, 'certs', 'ca_certificate.pem'));
    final srvCert = File(p.join(repoRoot.path, 'certs', 'server_certificate.pem'));
    if (caCert.existsSync() && srvCert.existsSync()) {
      certsOk = true;
    } else {
      certsError = 'Missing TLS certificates in certs/ directory';
    }
    items.add(PreflightItem(
      id: 'certs',
      name: 'TLS 1.3 & PQC Certificates',
      description: 'CA and server certificates for mTLS AMQP communication',
      isSatisfied: certsOk,
      errorOrWarning: certsError,
      isCritical: true,
    ));

    // 5. Check Smart Contract Artifacts
    bool contractOk = false;
    String? contractError;
    final contractAddr = File(p.join(repoRoot.path, 'contract_address.txt'));
    final contractAbi = File(p.join(repoRoot.path, 'contract_abi.json'));
    if (contractAddr.existsSync() && contractAbi.existsSync()) {
      contractOk = true;
    } else {
      contractError = 'contract_address.txt or contract_abi.json missing';
    }
    items.add(PreflightItem(
      id: 'contract',
      name: 'Blockchain Contract Artifacts',
      description: 'TelemetryRegistry ABI & deployment address for Besu ledger logging',
      isSatisfied: contractOk,
      errorOrWarning: contractError,
      isCritical: false,
    ));

    return PreflightReport(items: items, timestamp: DateTime.now());
  }

  /// Automatically executes `npm install` inside `dashboard-backend`
  Future<ProcessResult> installNodeDependencies() async {
    final backendDir = p.join(repoRoot.path, 'dashboard-backend');
    final npm = PlatformAdapter.getNpmExecutable();
    return await Process.run(npm, ['install'], workingDirectory: backendDir);
  }

  /// Automatically creates virtualenv
  Future<ProcessResult> createPythonVenv() async {
    return await Process.run('python', ['-m', 'venv', 'venv'], workingDirectory: repoRoot.path);
  }
}
