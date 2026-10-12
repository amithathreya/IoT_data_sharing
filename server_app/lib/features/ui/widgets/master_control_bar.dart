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
    Color badgeBg;
    Color badgeBorder;
    String badgeText;
    IconData badgeIcon;

    if (activeIncidents > 0) {
      badgeColor = AppTheme.statusRed;
      badgeBg = AppTheme.statusRedLight;
      badgeBorder = AppTheme.statusRedBorder;
      badgeText = '$activeIncidents INCIDENT${activeIncidents > 1 ? 'S' : ''} DETECTED';
      badgeIcon = Icons.warning_amber_rounded;
    } else if (status == OrchestratorStatus.running) {
      badgeColor = AppTheme.statusGreen;
      badgeBg = AppTheme.statusGreenLight;
      badgeBorder = AppTheme.statusGreenBorder;
      badgeText = 'ALL SYSTEMS OPERATIONAL';
      badgeIcon = Icons.check_circle_rounded;
    } else if (status == OrchestratorStatus.starting) {
      badgeColor = AppTheme.statusAmber;
      badgeBg = AppTheme.statusAmberLight;
      badgeBorder = AppTheme.statusAmberBorder;
      badgeText = 'BOOTSTRAPPING STACK...';
      badgeIcon = Icons.hourglass_top_rounded;
    } else if (status == OrchestratorStatus.stopping) {
      badgeColor = AppTheme.statusAmber;
      badgeBg = AppTheme.statusAmberLight;
      badgeBorder = AppTheme.statusAmberBorder;
      badgeText = 'SHUTTING DOWN...';
      badgeIcon = Icons.hourglass_bottom_rounded;
    } else {
      badgeColor = AppTheme.textSecondary;
      badgeBg = const Color(0xFFF8FAFC);
      badgeBorder = AppTheme.borderSubtle;
      badgeText = 'STACK STOPPED / IDLE';
      badgeIcon = Icons.radio_button_unchecked;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: const BoxDecoration(
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
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryBlue,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Center(
                    child: Icon(
                      Icons.shield_outlined,
                      color: Colors.white,
                      size: 22,
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Text(
                      'PQC SECURITY SERVER SUPERVISOR',
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                        letterSpacing: 0.6,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Post-Quantum IoT • Hyperledger Besu • Federated Learning',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
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
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: badgeBg,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: badgeBorder),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(badgeIcon, color: badgeColor, size: 14),
                  const SizedBox(width: 8),
                  Text(
                    badgeText,
                    style: TextStyle(
                      color: badgeColor,
                      fontSize: 11.5,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.5,
                    ),
                  ),
                  if (status == OrchestratorStatus.running) ...[
                    const SizedBox(width: 10),
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
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(width: 32),

            // ── Master Controls ──
            Row(
              children: [
                // Preflight Audit Button
                OutlinedButton.icon(
                  onPressed: onOpenPreflight,
                  icon: const Icon(Icons.fact_check_outlined, size: 16, color: AppTheme.textPrimary),
                  label: const Text('Preflight Audit'),
                  style: OutlinedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: AppTheme.textPrimary,
                    side: const BorderSide(color: AppTheme.borderSubtle),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                    textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),

                const SizedBox(width: 10),

                // Export Logs Button
                OutlinedButton.icon(
                  onPressed: onExportLogs,
                  icon: const Icon(Icons.file_download_outlined, size: 16, color: AppTheme.textPrimary),
                  label: const Text('Export Logs'),
                  style: OutlinedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: AppTheme.textPrimary,
                    side: const BorderSide(color: AppTheme.borderSubtle),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                    textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),

                const SizedBox(width: 10),

                // Master Restart Button
                OutlinedButton.icon(
                  onPressed: status == OrchestratorStatus.starting ||
                          status == OrchestratorStatus.stopping
                      ? null
                      : () => orchestrator.restartAll(),
                  icon: const Icon(Icons.refresh_rounded, size: 16, color: AppTheme.statusAmber),
                  label: const Text('Restart All'),
                  style: OutlinedButton.styleFrom(
                    backgroundColor: AppTheme.statusAmberLight,
                    foregroundColor: AppTheme.statusAmber,
                    side: const BorderSide(color: Color(0xFFFBBF24)),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                    textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),

                const SizedBox(width: 10),

                // Master Stop Button
                ElevatedButton.icon(
                  onPressed: status == OrchestratorStatus.idle ||
                          status == OrchestratorStatus.stopping
                      ? null
                      : () => orchestrator.stopAll(),
                  icon: const Icon(Icons.square, size: 11, color: AppTheme.statusRed),
                  label: const Text('Stop All'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.statusRedLight,
                    foregroundColor: AppTheme.statusRed,
                    elevation: 0,
                    side: const BorderSide(color: AppTheme.statusRedBorder),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                    textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),

                const SizedBox(width: 10),

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
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.play_arrow_rounded, size: 18, color: Colors.white),
                  label: Text(
                    status == OrchestratorStatus.starting ? 'Starting...' : 'START ALL SERVICES',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                      color: Colors.white,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
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
