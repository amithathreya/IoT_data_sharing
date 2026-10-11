import 'dart:io';
import 'package:flutter/material.dart';
import '../supervisor/services/orchestrator.dart';
import '../supervisor/services/process_supervisor.dart';
import '../terminal/services/log_aggregator.dart';
import '../../core/services/preflight_service.dart';
import 'widgets/master_control_bar.dart';
import 'widgets/preflight_banner.dart';
import 'widgets/preflight_dialog.dart';
import 'widgets/incidents_card.dart';
import 'widgets/service_grid.dart';
import 'widgets/terminal_console.dart';

class HomeScreen extends StatefulWidget {
  final Directory repoRoot;
  final bool enableWatchdog;

  const HomeScreen({
    super.key,
    required this.repoRoot,
    this.enableWatchdog = true,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final LogAggregator _logAggregator;
  late final ProcessSupervisor _supervisor;
  late final Orchestrator _orchestrator;
  late final PreflightService _preflightService;

  PreflightReport? _preflightReport;
  bool _isFixingNodeDeps = false;

  @override
  void initState() {
    super.initState();
    _logAggregator = LogAggregator();
    _supervisor = ProcessSupervisor(
      repoRoot: widget.repoRoot,
      logAggregator: _logAggregator,
      enableWatchdog: widget.enableWatchdog,
    );
    _orchestrator = Orchestrator(supervisor: _supervisor);
    _preflightService = PreflightService(widget.repoRoot);

    _supervisor.addListener(_onStateChanged);
    _orchestrator.addListener(_onStateChanged);

    // Initial preflight check
    if (widget.enableWatchdog) {
      _runPreflightAudit();
    }
  }

  @override
  void dispose() {
    _supervisor.removeListener(_onStateChanged);
    _orchestrator.removeListener(_onStateChanged);
    _supervisor.dispose();
    _orchestrator.dispose();
    _logAggregator.dispose();
    super.dispose();
  }

  void _onStateChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _runPreflightAudit() async {
    final report = await _preflightService.runAudit();
    if (mounted) {
      setState(() {
        _preflightReport = report;
      });
    }
  }

  Future<void> _installNodeDeps() async {
    setState(() => _isFixingNodeDeps = true);
    _logAggregator.addLog(
      serviceId: _supervisor.states.keys.first,
      text: 'Running npm install in dashboard-backend...',
    );

    final res = await _preflightService.installNodeDependencies();
    if (res.exitCode == 0) {
      _logAggregator.addLog(
        serviceId: _supervisor.states.keys.first,
        text: 'npm install completed successfully!',
      );
    } else {
      _logAggregator.addLog(
        serviceId: _supervisor.states.keys.first,
        text: 'npm install error: ${res.stderr}',
        isError: true,
      );
    }

    setState(() => _isFixingNodeDeps = false);
    await _runPreflightAudit();
  }

  void _showPreflightDialog() {
    if (_preflightReport == null) return;
    showDialog(
      context: context,
      builder: (ctx) => PreflightDialog(
        report: _preflightReport!,
        onRefresh: () async {
          Navigator.of(ctx).pop();
          await _runPreflightAudit();
          _showPreflightDialog();
        },
        onInstallNodeDeps: () async {
          Navigator.of(ctx).pop();
          await _installNodeDeps();
          _showPreflightDialog();
        },
        isFixingNodeDeps: _isFixingNodeDeps,
      ),
    );
  }

  Future<void> _exportLogs() async {
    try {
      final exportFile = await _logAggregator.exportLogs(widget.repoRoot);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Diagnostics exported to: ${exportFile.path}'),
            backgroundColor: Colors.teal,
            duration: const Duration(seconds: 4),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to export logs: $e'),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Master Header Bar
            MasterControlBar(
              orchestrator: _orchestrator,
              supervisor: _supervisor,
              logAggregator: _logAggregator,
              onOpenPreflight: _showPreflightDialog,
              onExportLogs: _exportLogs,
            ),

            // Main Scrollable Dashboard Content
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Preflight Warning Banner (if anything missing)
                    PreflightBanner(
                      report: _preflightReport,
                      onRefresh: _runPreflightAudit,
                      onInstallNodeDeps: _installNodeDeps,
                      isFixingNodeDeps: _isFixingNodeDeps,
                    ),

                    // Active Incidents Card
                    IncidentsCard(supervisor: _supervisor),

                    // 6 Service Cards Grid
                    ServiceGrid(supervisor: _supervisor),

                    // Unified Live Terminal Console
                    TerminalConsole(logAggregator: _logAggregator),

                    const SizedBox(height: 20),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
