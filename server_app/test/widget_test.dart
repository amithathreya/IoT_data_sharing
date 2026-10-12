import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:server_app/main.dart';

void main() {
  testWidgets('Server supervisor app smoke test', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      ServerSupervisorApp(
        repoRoot: Directory.current,
        enableWatchdog: false,
      ),
    );

    expect(find.text('PQC SECURITY SERVER SUPERVISOR'), findsOneWidget);
    expect(find.text('START ALL SERVICES'), findsOneWidget);
    expect(find.text('LIVE UNIFIED LOG STREAM'), findsOneWidget);
    expect(find.text('RabbitMQ Broker'), findsWidgets);
    expect(find.text('Hyperledger Besu'), findsWidgets);
    expect(find.text('Dashboard Backend'), findsWidgets);
    expect(find.text('Dashboard Frontend'), findsWidgets);
    expect(find.text('PQC Telemetry Consumer'), findsWidgets);
    expect(find.text('PQC Audio Consumer'), findsWidgets);
    expect(find.text('XFL Federated Server'), findsWidgets);
    expect(find.text('Grafana & Metrics'), findsWidgets);
  });
}
