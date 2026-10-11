import 'dart:async';
import 'dart:io';

class PortProbeResult {
  final int port;
  final bool isOpen;
  final int latencyMs;
  final String? error;

  PortProbeResult({
    required this.port,
    required this.isOpen,
    required this.latencyMs,
    this.error,
  });
}

class PortScannerService {
  /// Probes a single TCP port on localhost with a fast timeout
  static Future<PortProbeResult> probePort(
    int port, {
    String host = '127.0.0.1',
    Duration timeout = const Duration(milliseconds: 1000),
  }) async {
    final stopwatch = Stopwatch()..start();
    try {
      final socket = await Socket.connect(host, port, timeout: timeout);
      stopwatch.stop();
      await socket.close();
      return PortProbeResult(
        port: port,
        isOpen: true,
        latencyMs: stopwatch.elapsedMilliseconds,
      );
    } catch (e) {
      stopwatch.stop();
      return PortProbeResult(
        port: port,
        isOpen: false,
        latencyMs: stopwatch.elapsedMilliseconds,
        error: e.toString(),
      );
    }
  }

  /// Probes multiple ports concurrently
  static Future<Map<int, PortProbeResult>> probePorts(
    List<int> ports, {
    String host = '127.0.0.1',
  }) async {
    final futures = ports.map((p) => probePort(p, host: host));
    final results = await Future.wait(futures);
    return {for (var r in results) r.port: r};
  }

  /// Waits until a specific port opens or until maxTimeout expires
  static Future<bool> waitForPort(
    int port, {
    Duration maxTimeout = const Duration(seconds: 30),
    Duration pollInterval = const Duration(milliseconds: 1000),
    String host = '127.0.0.1',
  }) async {
    final endTime = DateTime.now().add(maxTimeout);
    while (DateTime.now().isBefore(endTime)) {
      final res = await probePort(port, host: host, timeout: pollInterval);
      if (res.isOpen) return true;
      await Future.delayed(pollInterval);
    }
    return false;
  }
}
