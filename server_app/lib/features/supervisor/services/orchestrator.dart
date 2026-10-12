import 'dart:async';
import 'package:flutter/foundation.dart';
import 'process_supervisor.dart';
import '../models/service_model.dart';
import '../../../core/services/port_scanner_service.dart';

enum OrchestratorStatus {
  idle,
  starting,
  running,
  stopping,
  error,
}

class Orchestrator extends ChangeNotifier {
  final ProcessSupervisor supervisor;

  OrchestratorStatus _status = OrchestratorStatus.idle;
  String _currentStepMessage = '';
  DateTime? _stackStartedAt;

  OrchestratorStatus get status => _status;
  String get currentStepMessage => _currentStepMessage;
  DateTime? get stackStartedAt => _stackStartedAt;

  Duration? get stackUptime {
    if (_stackStartedAt == null || _status != OrchestratorStatus.running) return null;
    return DateTime.now().difference(_stackStartedAt!);
  }

  String get stackUptimeFormatted {
    final up = stackUptime;
    if (up == null) return '--:--:--';
    final hours = up.inHours.toString().padLeft(2, '0');
    final minutes = (up.inMinutes % 60).toString().padLeft(2, '0');
    final seconds = (up.inSeconds % 60).toString().padLeft(2, '0');
    return '$hours:$minutes:$seconds';
  }

  Orchestrator({required this.supervisor});

  /// Starts all components with dependency-aware sequencing
  Future<bool> startAll() async {
    if (_status == OrchestratorStatus.starting || _status == OrchestratorStatus.running) {
      return true;
    }

    _status = OrchestratorStatus.starting;
    _currentStepMessage = 'Initializing stack startup sequence...';
    notifyListeners();

    try {
      // ── Step 1: Start Docker Infrastructure ──────────────────
      _currentStepMessage = 'Step 1/5: Starting Docker Infrastructure (RabbitMQ, Besu, Grafana)...';
      notifyListeners();

      final infrastructureStarted = await Future.wait([
        supervisor.startService(ServiceId.rabbitmq),
        supervisor.startService(ServiceId.besu),
        supervisor.startService(ServiceId.grafana),
      ]);
      if (infrastructureStarted.any((started) => !started)) {
        throw StateError('One or more Docker infrastructure services failed to start');
      }

      // ── Step 2: Health Gate for Infrastructure ───────────────
      _currentStepMessage = 'Step 2/5: Awaiting RabbitMQ (5671) & Besu (8545) Port Readiness...';
      notifyListeners();

      final rabbitReady = await PortScannerService.waitForPort(
        5671,
        maxTimeout: const Duration(seconds: 25),
      );
      if (!rabbitReady) {
        supervisor.logAggregator.addLog(
          serviceId: ServiceId.rabbitmq,
          text: 'Warning: RabbitMQ port 5671 did not open within 25s, continuing anyway...',
          isError: true,
        );
      }

      final besuReady = await PortScannerService.waitForPort(
        8545,
        maxTimeout: const Duration(seconds: 25),
      );
      if (!besuReady) {
        supervisor.logAggregator.addLog(
          serviceId: ServiceId.besu,
          text: 'Warning: Besu RPC port 8545 did not open within 25s, continuing anyway...',
          isError: true,
        );
      }

      // ── Step 3: Start Node Dashboard Backend ─────────────────
      _currentStepMessage = 'Step 3/5: Launching Dashboard Backend (Node.js :4000)...';
      notifyListeners();

      if (!await supervisor.startService(ServiceId.dashboardBackend)) {
        throw StateError('Dashboard backend failed to start');
      }

      // Wait for port 4000
      final backendReady = await PortScannerService.waitForPort(
        4000,
        maxTimeout: const Duration(seconds: 10),
      );
      if (!backendReady) {
        throw StateError('Dashboard backend did not open port 4000');
      }

      _currentStepMessage = 'Step 4/6: Launching Dashboard Frontend (Vite :5173)...';
      notifyListeners();
      if (!await supervisor.startService(ServiceId.dashboardFrontend)) {
        throw StateError('Dashboard frontend failed to start');
      }

      final frontendReady = await PortScannerService.waitForPort(
        5173,
        maxTimeout: const Duration(seconds: 10),
      );
      if (!frontendReady) {
        throw StateError('Dashboard frontend did not open port 5173');
      }

      // ── Step 4: Start Python Federated Learning Server ────────
      _currentStepMessage = 'Step 4/5: Launching XFL Federated Learning Server...';
      notifyListeners();

      if (!await supervisor.startService(ServiceId.xflServer)) {
        throw StateError('XFL server failed to start');
      }

      // Short delay for FL exchange initialization
      await Future.delayed(const Duration(seconds: 2));

      // ── Step 5: Start Python PQC Telemetry & Audio Consumers ────
      _currentStepMessage = 'Step 5/6: Launching PQC Telemetry Consumer (server.py)...';
      notifyListeners();
      if (!await supervisor.startService(ServiceId.consumer)) {
        throw StateError('Telemetry consumer failed to start');
      }

      _currentStepMessage = 'Step 6/6: Launching PQC Audio Consumer (audio_consumer.py)...';
      notifyListeners();
      if (!await supervisor.startService(ServiceId.audioConsumer)) {
        throw StateError('Audio consumer failed to start');
      }

      _status = OrchestratorStatus.running;
      _currentStepMessage = 'All server services running!';
      _stackStartedAt = DateTime.now();
      notifyListeners();
      return true;
    } catch (e) {
      _status = OrchestratorStatus.error;
      _currentStepMessage = 'Startup failed: $e';
      notifyListeners();
      return false;
    }
  }

  /// Stops all running services cleanly in reverse order
  Future<void> stopAll() async {
    _status = OrchestratorStatus.stopping;
    _currentStepMessage = 'Stopping all services...';
    notifyListeners();

    try {
      // 1. Stop Python workers
      await supervisor.stopService(ServiceId.audioConsumer);
      await supervisor.stopService(ServiceId.consumer);
      await supervisor.stopService(ServiceId.xflServer);

      // 2. Stop Node backend
      await supervisor.stopService(ServiceId.dashboardFrontend);
      await supervisor.stopService(ServiceId.dashboardBackend);

      // 3. Stop Docker services
      await supervisor.stopService(ServiceId.rabbitmq);
      await supervisor.stopService(ServiceId.besu);
      await supervisor.stopService(ServiceId.grafana);

      _status = OrchestratorStatus.idle;
      _currentStepMessage = 'All services stopped.';
      _stackStartedAt = null;
    } catch (e) {
      _status = OrchestratorStatus.error;
      _currentStepMessage = 'Stop error: $e';
    } finally {
      notifyListeners();
    }
  }

  /// Full sequential restart of all components
  Future<void> restartAll() async {
    await stopAll();
    await Future.delayed(const Duration(seconds: 2));
    await startAll();
  }
}
