enum ServiceId {
  rabbitmq,
  besu,
  dashboardBackend,
  dashboardFrontend,
  consumer,
  audioConsumer,
  xflServer,
  grafana,
}

enum ServiceStatus {
  stopped,
  starting,
  running,
  stopping,
  crashed,
  warning,
}

enum ServiceType {
  docker,
  node,
  python,
}

class ServiceConfig {
  final ServiceId id;
  final String displayName;
  final ServiceType type;
  final String description;
  final int? primaryPort;
  final List<int> allPorts;
  final String? webUiUrl;
  final String? scriptPath; // relative to repo root
  final String? workingDir; // relative to repo root

  const ServiceConfig({
    required this.id,
    required this.displayName,
    required this.type,
    required this.description,
    this.primaryPort,
    this.allPorts = const [],
    this.webUiUrl,
    this.scriptPath,
    this.workingDir,
  });

  static const List<ServiceConfig> allServices = [
    ServiceConfig(
      id: ServiceId.rabbitmq,
      displayName: 'RabbitMQ Broker',
      type: ServiceType.docker,
      description: 'TLS 1.3 Post-Quantum AMQP Broker & Message Queues',
      primaryPort: 5671,
      allPorts: [5671, 5672, 15672],
      webUiUrl: 'http://localhost:15672',
    ),
    ServiceConfig(
      id: ServiceId.besu,
      displayName: 'Hyperledger Besu',
      type: ServiceType.docker,
      description: 'Private IBFT 2.0 Blockchain Ledger (TelemetryRegistry.sol)',
      primaryPort: 8545,
      allPorts: [8545, 8080],
      webUiUrl: 'http://localhost:8080',
      workingDir: 'besu-network',
    ),
    ServiceConfig(
      id: ServiceId.dashboardBackend,
      displayName: 'Dashboard Backend',
      type: ServiceType.node,
      description: 'Node.js Express & Socket.IO Telemetry Ingestion Hub',
      primaryPort: 4000,
      allPorts: [4000],
      scriptPath: 'server.js',
      workingDir: 'dashboard-backend',
    ),
    ServiceConfig(
      id: ServiceId.dashboardFrontend,
      displayName: 'Dashboard Frontend',
      type: ServiceType.node,
      description: 'Vite React telemetry dashboard on port 5173',
      primaryPort: 5173,
      allPorts: [5173],
      webUiUrl: 'http://localhost:5173',
      scriptPath: 'package.json',
      workingDir: 'dashboard-frontend',
    ),
    ServiceConfig(
      id: ServiceId.consumer,
      displayName: 'PQC Telemetry Consumer',
      type: ServiceType.docker,
      description: 'ML-KEM/ML-DSA decryptor, sensor telemetry & Besu logger',
    ),
    ServiceConfig(
      id: ServiceId.audioConsumer,
      displayName: 'PQC Audio Consumer',
      type: ServiceType.docker,
      description: 'ML-KEM/ML-DSA live audio stream decryptor & Besu logger',
    ),
    ServiceConfig(
      id: ServiceId.xflServer,
      displayName: 'XFL Federated Server',
      type: ServiceType.docker,
      description: 'Post-Quantum Federated Learning Global Aggregator',
    ),
    ServiceConfig(
      id: ServiceId.grafana,
      displayName: 'Grafana & Metrics',
      type: ServiceType.docker,
      description: 'Time-Series Telemetry Dashboard & Alethio Explorer',
      primaryPort: 3000,
      allPorts: [3000, 8080],
      webUiUrl: 'http://localhost:3000',
    ),
  ];
}

class ServiceState {
  final ServiceConfig config;
  ServiceStatus status;
  int? pid;
  bool isPortOpen;
  int? portLatencyMs;
  DateTime? startedAt;
  int? exitCode;
  String? lastError;

  ServiceState({
    required this.config,
    this.status = ServiceStatus.stopped,
    this.pid,
    this.isPortOpen = false,
    this.portLatencyMs,
    this.startedAt,
    this.exitCode,
    this.lastError,
  });

  Duration? get uptime {
    if (startedAt == null || status != ServiceStatus.running) return null;
    return DateTime.now().difference(startedAt!);
  }

  String get uptimeFormatted {
    final up = uptime;
    if (up == null) return '--:--';
    final hours = up.inHours.toString().padLeft(2, '0');
    final minutes = (up.inMinutes % 60).toString().padLeft(2, '0');
    final seconds = (up.inSeconds % 60).toString().padLeft(2, '0');
    return '$hours:$minutes:$seconds';
  }
}
