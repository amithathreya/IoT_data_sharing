import '../../supervisor/models/service_model.dart';

class LogEntry {
  final DateTime timestamp;
  final ServiceId serviceId;
  final String text;
  final bool isError;
  final bool isWarning;

  LogEntry({
    required this.timestamp,
    required this.serviceId,
    required this.text,
    this.isError = false,
    this.isWarning = false,
  });

  String get timeFormatted {
    final h = timestamp.hour.toString().padLeft(2, '0');
    final m = timestamp.minute.toString().padLeft(2, '0');
    final s = timestamp.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }
}
