import 'service_model.dart';

enum IncidentSeverity {
  critical,
  warning,
  info,
}

class IncidentRecord {
  final String id;
  final ServiceId? serviceId;
  final String title;
  final String details;
  final DateTime timestamp;
  final IncidentSeverity severity;
  bool isResolved;

  IncidentRecord({
    required this.id,
    this.serviceId,
    required this.title,
    required this.details,
    required this.timestamp,
    required this.severity,
    this.isResolved = false,
  });

  String get timeFormatted {
    final h = timestamp.hour.toString().padLeft(2, '0');
    final m = timestamp.minute.toString().padLeft(2, '0');
    final s = timestamp.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }
}
