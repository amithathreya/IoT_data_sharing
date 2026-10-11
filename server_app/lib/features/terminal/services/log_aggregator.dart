import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import '../models/log_entry.dart';
import '../../supervisor/models/service_model.dart';

class LogAggregator extends ChangeNotifier {
  static const int maxCapacity = 5000;
  final List<LogEntry> _logs = [];

  ServiceId? _selectedFilter;
  bool _errorsOnly = false;
  String _searchQuery = '';

  ServiceId? get selectedFilter => _selectedFilter;
  bool get errorsOnly => _errorsOnly;
  String get searchQuery => _searchQuery;

  List<LogEntry> get allLogs => List.unmodifiable(_logs);

  List<LogEntry> get filteredLogs {
    return _logs.where((entry) {
      if (_selectedFilter != null && entry.serviceId != _selectedFilter) {
        return false;
      }
      if (_errorsOnly && !entry.isError) {
        return false;
      }
      if (_searchQuery.isNotEmpty &&
          !entry.text.toLowerCase().contains(_searchQuery.toLowerCase())) {
        return false;
      }
      return true;
    }).toList();
  }

  void addLog({
    required ServiceId serviceId,
    required String text,
    bool isError = false,
  }) {
    // Detect errors / warnings from string contents if not explicitly tagged
    final lower = text.toLowerCase();
    final detectedError = isError ||
        lower.contains('error') ||
        lower.contains('exception') ||
        lower.contains('traceback') ||
        lower.contains('fatal') ||
        lower.contains('failed');
    final detectedWarning = !detectedError &&
        (lower.contains('warn') || lower.contains('timeout') || lower.contains('dropped'));

    final entry = LogEntry(
      timestamp: DateTime.now(),
      serviceId: serviceId,
      text: text,
      isError: detectedError,
      isWarning: detectedWarning,
    );

    _logs.add(entry);
    if (_logs.length > maxCapacity) {
      _logs.removeAt(0);
    }
    notifyListeners();
  }

  void setFilter(ServiceId? serviceId) {
    _selectedFilter = serviceId;
    notifyListeners();
  }

  void setErrorsOnly(bool value) {
    _errorsOnly = value;
    notifyListeners();
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  void clearLogs() {
    _logs.clear();
    notifyListeners();
  }

  /// Exports the log buffer to a text file in the repository root or desktop
  Future<File> exportLogs(Directory destinationDir) async {
    final now = DateTime.now();
    final timestamp =
        '${now.year}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}_${now.hour.toString().padLeft(2, '0')}${now.minute.toString().padLeft(2, '0')}${now.second.toString().padLeft(2, '0')}';
    final file = File(p.join(destinationDir.path, 'server_diagnostic_$timestamp.log'));

    final buffer = StringBuffer();
    buffer.writeln('======================================================');
    buffer.writeln('PQC IOT TELEMETRY SERVER DIAGNOSTIC EXPORT');
    buffer.writeln('Export Time: ${now.toIso8601String()}');
    buffer.writeln('Total Log Lines: ${_logs.length}');
    buffer.writeln('======================================================\n');

    for (final entry in _logs) {
      final tag = entry.serviceId.name.toUpperCase().padRight(16);
      final level = entry.isError ? '[ERROR]' : (entry.isWarning ? '[WARN] ' : '[INFO] ');
      buffer.writeln('[${entry.timeFormatted}] $level $tag ${entry.text}');
    }

    return await file.writeAsString(buffer.toString());
  }
}
