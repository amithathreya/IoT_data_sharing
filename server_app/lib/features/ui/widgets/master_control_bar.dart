import 'package:flutter/material.dart';
import '../../supervisor/services/orchestrator.dart';
import '../../supervisor/services/process_supervisor.dart';
import '../../terminal/services/log_aggregator.dart';
import '../../../core/theme/app_theme.dart';

class MasterControlBar extends StatelessWidget {
  final Orchestrator orchestrator;
  final ProcessSupervisor supervisor;
  final LogAggregator logAggregator;
  final VoidCallback onOpenPreflight;
  final VoidCallback onExportLogs;

  const MasterControlBar({
    super.key,
    required this.orchestrator,
    required this.supervisor,
    required this.logAggregator,
    required this.onOpenPreflight,
    required this.onExportLogs,
  });

  @override
  Widget build(BuildContext context) {
    final status = orchestrator.status;
    final activeIncidents = supervisor.activeIncidentCount;

    Color badgeColor;
    String badgeText;
    IconData badgeIcon;

    if (activeIncidents > 0) {
      badgeColor = AppTheme.statusRed;
      badgeText = '$activeIncidents INCIDENT${activeIncidents > 1 ? 'S' : ''} DETECTED';
      badgeIcon = Icons.warning_amber_rounded;
    } else if (status == OrchestratorStatus.running) {
      badgeColor = AppTheme.statusGreen;
      badgeText = 'ALL SYSTEMS OPERATIONAL';
      badgeIcon = Icons.check_circle_rounded;
    } else if (status == OrchestratorStatus.starting) {
      badgeColor = AppTheme.statusAmber;
      badgeText = 'BOOTSTRAPPING STACK...';
      badgeIcon = Icons.hourglass_top_rounded;
    } else if (status == OrchestratorStatus.stopping) {
      badgeColor = AppTheme.statusAmber;
      badgeText = 'SHUTTING DOWN...';
      badgeIcon = Icons.hourglass_bottom_rounded;
    } else {
      badgeColor = AppTheme.textMuted;
      badgeText = 'STACK STOPPED / IDLE';
      badgeIcon = Icons.stop_circle_outlined;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        border: Border(
          bottom: BorderSide(color: AppTheme.border, width: 1),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
          // ── App Brand & Logo ──
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.statusCyan.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.statusCyan.withOpacity(0.3)),
                ),
                child: const Icon(
                  Icons.shield_outlined,
                  color: AppTheme.statusCyan,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'PQC SECURITY SERVER SUPERVISOR',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 15,
                      letterSpacing: 1.1,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  Text(
                    'Post-Quantum IoT • Hyperledger Besu • Federated Learning',
                    style: TextStyle(
                      fontSize: 11,
                      color: AppTheme.textMuted,
                    ),
                  ),
                ],
              ),
            ],
          ),

          const SizedBox(width: 24),

          // ── Global Status Pill ──
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: badgeColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: badgeColor.withOpacity(0.4)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(badgeIcon, color: badgeColor, size: 16),
                const SizedBox(width: 8),
                Text(
                  badgeText,
                  style: TextStyle(
                    color: badgeColor,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.5,
                  ),
                ),
                if (status == OrchestratorStatus.running) ...[
                  const SizedBox(width: 12),
                  Container(
                    width: 4,
                    height: 4,
                    decoration: BoxDecoration(
                      color: badgeColor,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Uptime: ${orchestrator.stackUptimeFormatted}',
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 11,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(width: 32),

          // ── Master Controls ──
          Wrap(
            spacing: 10,
            children: [
              // Preflight Audit Button
              OutlinedButton.icon(
                onPressed: onOpenPreflight,
                icon: const Icon(Icons.fact_check_outlined, size: 16),
                label: const Text('Preflight Audit'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                ),
              ),

              // Export Logs Button
              OutlinedButton.icon(
                onPressed: onExportLogs,
                icon: const Icon(Icons.download_rounded, size: 16),
                label: const Text('Export Logs'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                ),
              ),

              // Master Restart Button
              OutlinedButton.icon(
                onPressed: status == OrchestratorStatus.starting ||
                        status == OrchestratorStatus.stopping
                    ? null
                    : () => orchestrator.restartAll(),
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Restart All'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.statusAmber,
                  side: BorderSide(color: AppTheme.statusAmber.withOpacity(0.5)),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                ),
              ),

              // Master Stop Button
              ElevatedButton.icon(
                onPressed: status == OrchestratorStatus.idle ||
                        status == OrchestratorStatus.stopping
                    ? null
                    : () => orchestrator.stopAll(),
                icon: const Icon(Icons.stop_rounded, size: 18),
                label: const Text('Stop All'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.statusRed.withOpacity(0.18),
                  foregroundColor: AppTheme.statusRed,
                  side: BorderSide(color: AppTheme.statusRed.withOpacity(0.5)),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),

              // Master Start All Button
              ElevatedButton.icon(
                onPressed: status == OrchestratorStatus.starting ||
                        status == OrchestratorStatus.running
                    ? null
                    : () => orchestrator.startAll(),
                icon: status == OrchestratorStatus.starting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppTheme.statusGreen,
                        ),
                      )
                    : const Icon(Icons.play_arrow_rounded, size: 20),
                label: Text(
                  status == OrchestratorStatus.starting ? 'Starting...' : 'START ALL SERVICES',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.statusGreen.withOpacity(0.2),
                  foregroundColor: AppTheme.statusGreen,
                  side: BorderSide(color: AppTheme.statusGreen.withOpacity(0.6)),
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                ),
              ),
            ],
          ),
        ],
        ),
      ),
    );
  }
}
