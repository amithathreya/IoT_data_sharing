import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import '../models/service_model.dart';
import '../models/incident_model.dart';
import '../../terminal/services/log_aggregator.dart';
import '../../../core/platform/platform_adapter.dart';
import '../../../core/services/port_scanner_service.dart';

class ProcessSupervisor extends ChangeNotifier {
  final Directory repoRoot;
  final LogAggregator logAggregator;

  final Map<ServiceId, ServiceState> _states = {};
  final Map<ServiceId, Process> _runningProcesses = {};
  final List<IncidentRecord> _incidents = [];

  Timer? _healthWatchdogTimer;

  Map<ServiceId, ServiceState> get states => Map.unmodifiable(_states);
  List<IncidentRecord> get incidents => List.unmodifiable(_incidents);
  int get activeIncidentCount => _incidents.where((i) => !i.isResolved).length;

  ProcessSupervisor({
    required this.repoRoot,
    required this.logAggregator,
    bool enableWatchdog = true,
  }) {
    // Initialize default states for all services
    for (final cfg in ServiceConfig.allServices) {
      _states[cfg.id] = ServiceState(config: cfg);
    }
    if (enableWatchdog) {
      _startWatchdog();
    }
  }

  ServiceState getState(ServiceId id) => _states[id]!;

  /// Starts the background watchdog that probes ports and checks Docker container status
  void _startWatchdog() {
    _healthWatchdogTimer?.cancel();
    _healthWatchdogTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      await _checkHealthAll();
    });
  }

  @override
  void dispose() {
    _healthWatchdogTimer?.cancel();
    super.dispose();
  }

  /// Probes ports for all configured services and checks state
  Future<void> _checkHealthAll() async {
    for (final config in ServiceConfig.allServices) {
      final state = _states[config.id]!;
      if (config.primaryPort != null) {
        final probe = await PortScannerService.probePort(config.primaryPort!);
        final wasOpen = state.isPortOpen;
        state.isPortOpen = probe.isOpen;
        state.portLatencyMs = probe.isOpen ? probe.latencyMs : null;

        // If port opened and status was starting, transition to running
        if (probe.isOpen && state.status == ServiceStatus.starting) {
          state.status = ServiceStatus.running;
          state.startedAt ??= DateTime.now();
        }

        // If port closed while status was running (e.g. external kill or container stopped)
        if (!probe.isOpen && wasOpen && state.status == ServiceStatus.running) {
          if (config.type == ServiceType.docker) {
            state.status = ServiceStatus.stopped;
          }
        }
      } else if (config.type == ServiceType.docker) {
        if (state.status == ServiceStatus.running || state.status == ServiceStatus.starting) {
          final isRunning = await _isDockerContainerRunning(config.id);
          if (isRunning && state.status == ServiceStatus.starting) {
            state.status = ServiceStatus.running;
            state.startedAt ??= DateTime.now();
          } else if (!isRunning && state.status == ServiceStatus.running) {
            state.status = ServiceStatus.stopped;
          }
        }
      }
    }
    notifyListeners();
  }

  /// Starts a specific service
  Future<bool> startService(ServiceId id) async {
    final state = _states[id]!;
    if (state.status == ServiceStatus.running || state.status == ServiceStatus.starting) {
      return true;
    }

    state.status = ServiceStatus.starting;
    state.lastError = null;
    notifyListeners();

    logAggregator.addLog(
      serviceId: id,
      text: 'Starting ${state.config.displayName}...',
    );

    try {
      if (state.config.type == ServiceType.docker) {
        return await _startDockerService(id);
      } else if (state.config.type == ServiceType.node) {
        return await _startNodeService(id);
      } else if (state.config.type == ServiceType.python) {
        return await _startPythonService(id);
      }
      return false;
    } catch (e, stack) {
      state.status = ServiceStatus.crashed;
      state.lastError = e.toString();
      _registerIncident(
        serviceId: id,
        title: '${state.config.displayName} Failed to Start',
        details: '$e\n$stack',
        severity: IncidentSeverity.critical,
      );
      logAggregator.addLog(
        serviceId: id,
        text: 'Error launching service: $e',
        isError: true,
      );
      notifyListeners();
      return false;
    }
  }

  /// Stops a specific service
  Future<void> stopService(ServiceId id) async {
    final state = _states[id]!;
    state.status = ServiceStatus.stopping;
    notifyListeners();

    logAggregator.addLog(
      serviceId: id,
      text: 'Stopping ${state.config.displayName}...',
    );

    try {
      if (state.config.type == ServiceType.docker) {
        await _stopDockerService(id);
      } else {
        final proc = _runningProcesses.remove(id);
        if (proc != null) {
          await PlatformAdapter.killProcessTree(proc.pid);
        }
      }
    } catch (e) {
      logAggregator.addLog(
        serviceId: id,
        text: 'Error stopping service: $e',
        isError: true,
      );
    } finally {
      state.status = ServiceStatus.stopped;
      state.pid = null;
      state.startedAt = null;
      notifyListeners();
    }
  }

  /// Restarts a specific service
  Future<void> restartService(ServiceId id) async {
    await stopService(id);
    await Future.delayed(const Duration(milliseconds: 800));
    await startService(id);
  }

  // ── Docker Start & Stop ─────────────────────────────────────────

  Future<bool> _startDockerService(ServiceId id) async {
    final state = _states[id]!;
    final dockerCmd = PlatformAdapter.getDockerExecutable();

    String workDir = repoRoot.path;
    List<String> args;
    String serviceName = '';

    if (id == ServiceId.besu) {
      workDir = p.join(repoRoot.path, 'besu-network');
      args = ['compose', 'up', '-d'];
    } else {
      switch (id) {
        case ServiceId.rabbitmq:
          serviceName = 'rabbitmq';
          break;
        case ServiceId.grafana:
          serviceName = 'grafana';
          break;
        case ServiceId.consumer:
          serviceName = 'consumer';
          break;
        case ServiceId.audioConsumer:
          serviceName = 'audio-consumer';
          break;
        case ServiceId.xflServer:
          serviceName = 'xfl';
          break;
        default:
          serviceName = '';
      }
      args = ['compose', 'up', '-d', serviceName];
    }

    final result = await Process.run(
      dockerCmd,
      args,
      workingDirectory: workDir,
    );

    if (result.exitCode == 0) {
      logAggregator.addLog(
        serviceId: id,
        text: 'Docker container started: ${result.stdout.toString().trim()}',
      );

      if (state.config.primaryPort == null) {
        state.status = ServiceStatus.running;
        state.startedAt = DateTime.now();
      }

      // Stream docker container logs live to console
      if (serviceName.isNotEmpty) {
        try {
          final logProc = await Process.start(
            dockerCmd,
            ['compose', 'logs', '-f', serviceName],
            workingDirectory: workDir,
            mode: ProcessStartMode.normal,
          );
          _runningProcesses[id] = logProc;

          logProc.stdout
              .transform(utf8.decoder)
              .transform(const LineSplitter())
              .listen((line) {
            if (line.isNotEmpty) {
              logAggregator.addLog(serviceId: id, text: line);
            }
          });
          logProc.stderr
              .transform(utf8.decoder)
              .transform(const LineSplitter())
              .listen((line) {
            if (line.isNotEmpty) {
              logAggregator.addLog(serviceId: id, text: line, isError: true);
            }
          });
        } catch (_) {}
      }

      notifyListeners();
      return true;
    } else {
      final err = result.stderr.toString().trim();
      state.status = ServiceStatus.crashed;
      state.lastError = err;
      _registerIncident(
        serviceId: id,
        title: 'Docker Startup Failed (${state.config.displayName})',
        details: err,
        severity: IncidentSeverity.critical,
      );
      logAggregator.addLog(
        serviceId: id,
        text: 'Docker compose error: $err',
        isError: true,
      );
      notifyListeners();
      return false;
    }
  }

  Future<void> _stopDockerService(ServiceId id) async {
    final logProc = _runningProcesses.remove(id);
    if (logProc != null) {
      await PlatformAdapter.killProcessTree(logProc.pid);
    }

    final dockerCmd = PlatformAdapter.getDockerExecutable();
    String workDir = repoRoot.path;
    List<String> args;

    if (id == ServiceId.besu) {
      workDir = p.join(repoRoot.path, 'besu-network');
      args = ['compose', 'stop'];
    } else {
      String serviceName;
      switch (id) {
        case ServiceId.rabbitmq:
          serviceName = 'rabbitmq';
          break;
        case ServiceId.grafana:
          serviceName = 'grafana';
          break;
        case ServiceId.consumer:
          serviceName = 'consumer';
          break;
        case ServiceId.audioConsumer:
          serviceName = 'audio-consumer';
          break;
        case ServiceId.xflServer:
          serviceName = 'xfl';
          break;
        default:
          serviceName = '';
      }
      args = ['compose', 'stop', serviceName];
    }

    await Process.run(dockerCmd, args, workingDirectory: workDir);
  }

  Future<bool> _isDockerContainerRunning(ServiceId id) async {
    final dockerCmd = PlatformAdapter.getDockerExecutable();
    String serviceName;
    switch (id) {
      case ServiceId.consumer:
        serviceName = 'consumer';
        break;
      case ServiceId.audioConsumer:
        serviceName = 'audio-consumer';
        break;
      case ServiceId.xflServer:
        serviceName = 'xfl';
        break;
      case ServiceId.rabbitmq:
        serviceName = 'rabbitmq';
        break;
      case ServiceId.grafana:
        serviceName = 'grafana';
        break;
      default:
        return false;
    }

    try {
      final res = await Process.run(
        dockerCmd,
        ['compose', 'ps', '--services', '--filter', 'status=running'],
        workingDirectory: repoRoot.path,
      );
      if (res.exitCode == 0) {
        final lines = res.stdout.toString().split(RegExp(r'\r?\n'));
        return lines.map((l) => l.trim()).contains(serviceName);
      }
    } catch (_) {}
    return false;
  }

  // ── Node.js Start ───────────────────────────────────────────────

  Future<bool> _startNodeService(ServiceId id) async {
    final state = _states[id]!;
    final isFrontend = id == ServiceId.dashboardFrontend;
    final executable = isFrontend
        ? PlatformAdapter.getNpmExecutable()
        : PlatformAdapter.getNodeExecutable();
    final scriptPath = state.config.scriptPath!;
    final workDir = p.join(repoRoot.path, state.config.workingDir ?? '');
    final arguments = isFrontend
        ? ['run', 'dev', '--', '--host', '127.0.0.1']
        : [scriptPath];

    // Spawn native child process
    final process = await Process.start(
      executable,
      arguments,
      workingDirectory: workDir,
      mode: ProcessStartMode.normal,
      runInShell: PlatformAdapter.isWindows,
    );

    _runningProcesses[id] = process;
    state.pid = process.pid;
    state.status = ServiceStatus.running;
    state.startedAt = DateTime.now();
    notifyListeners();

    _wireProcessStreams(id, process);
    return true;
  }

  // ── Python Start ────────────────────────────────────────────────

  Future<bool> _startPythonService(ServiceId id) async {
    final state = _states[id]!;
    final pythonExe = PlatformAdapter.getPythonExecutable(repoRoot);
    final scriptPath = state.config.scriptPath!;
    final workDir = p.join(repoRoot.path, state.config.workingDir ?? '');

    // Spawn native child process unbuffered (-u flag for real-time stdout)
    final process = await Process.start(
      pythonExe,
      ['-u', scriptPath],
      workingDirectory: workDir,
      mode: ProcessStartMode.normal,
    );

    _runningProcesses[id] = process;
    state.pid = process.pid;
    state.status = ServiceStatus.running;
    state.startedAt = DateTime.now();
    notifyListeners();

    _wireProcessStreams(id, process);
    return true;
  }

  // ── Process Output & Crash Wiring ──────────────────────────────

  void _wireProcessStreams(ServiceId id, Process process) {
    final state = _states[id]!;

    // Stdout listener
    process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
      logAggregator.addLog(serviceId: id, text: line);
    });

    // Stderr listener
    process.stderr
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
      logAggregator.addLog(serviceId: id, text: line, isError: true);
    });

    // Zero-latency crash & termination listener
    process.exitCode.then((code) {
      _runningProcesses.remove(id);
      state.exitCode = code;
      state.pid = null;

      if (state.status != ServiceStatus.stopping) {
        // Unexpected exit (crash)
        state.status = code == 0 ? ServiceStatus.stopped : ServiceStatus.crashed;
        if (code != 0) {
          state.lastError = 'Process terminated with non-zero exit code: $code';
          _registerIncident(
            serviceId: id,
            title: '${state.config.displayName} Crashed (Code $code)',
            details: 'Service PID was ${process.pid}. Check terminal logs for traceback.',
            severity: IncidentSeverity.critical,
          );
        }
      } else {
        state.status = ServiceStatus.stopped;
      }
      notifyListeners();
    });
  }

  // ── Incident Management ─────────────────────────────────────────

  void _registerIncident({
    ServiceId? serviceId,
    required String title,
    required String details,
    required IncidentSeverity severity,
  }) {
    final incident = IncidentRecord(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      serviceId: serviceId,
      title: title,
      details: details,
      timestamp: DateTime.now(),
      severity: severity,
    );
    _incidents.insert(0, incident);
    notifyListeners();
  }

  void resolveIncident(String id) {
    final idx = _incidents.indexWhere((i) => i.id == id);
    if (idx != -1) {
      _incidents[idx].isResolved = true;
      notifyListeners();
    }
  }

  void clearAllIncidents() {
    _incidents.clear();
    notifyListeners();
  }
}
