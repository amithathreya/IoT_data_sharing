import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:server_app/features/supervisor/models/service_model.dart';
import 'package:server_app/features/terminal/services/log_aggregator.dart';
import 'package:server_app/core/services/port_scanner_service.dart';

void main() {
  group('LogAggregator Tests', () {
    test('Logs are added, auto-flagged for errors, and filterable', () {
      final aggregator = LogAggregator();

      aggregator.addLog(
        serviceId: ServiceId.consumer,
        text: 'Normal telemetry packet received',
      );
      aggregator.addLog(
        serviceId: ServiceId.consumer,
        text: 'Traceback (most recent call last): ConnectionError',
      );
      aggregator.addLog(
        serviceId: ServiceId.rabbitmq,
        text: 'AMQP broker listening on port 5671',
      );

      expect(aggregator.allLogs.length, 3);
      expect(aggregator.allLogs[1].isError, true);

      // Filter by service
      aggregator.setFilter(ServiceId.consumer);
      expect(aggregator.filteredLogs.length, 2);

      // Filter by error only
      aggregator.setErrorsOnly(true);
      expect(aggregator.filteredLogs.length, 1);
      expect(aggregator.filteredLogs.first.text, contains('ConnectionError'));
    });

    test('Log export produces formatted diagnostic file', () async {
      final aggregator = LogAggregator();
      aggregator.addLog(serviceId: ServiceId.besu, text: 'Block #100 mined');

      final tempDir = await Directory.systemTemp.createTemp('pqc_test');
      final exportFile = await aggregator.exportLogs(tempDir);

      expect(exportFile.existsSync(), true);
      final content = await exportFile.readAsString();
      expect(content, contains('PQC IOT TELEMETRY SERVER DIAGNOSTIC EXPORT'));
      expect(content, contains('Block #100 mined'));

      await tempDir.delete(recursive: true);
    });
  });

  group('PortScannerService Tests', () {
    test('Port scanner cleanly reports closed ports without crashing', () async {
      // Pick an unused ephemeral port
      final result = await PortScannerService.probePort(59999, timeout: const Duration(milliseconds: 200));
      expect(result.isOpen, false);
      expect(result.port, 59999);
    });
  });
}
