import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../supervisor/models/service_model.dart';
import '../../supervisor/services/process_supervisor.dart';
import '../../../core/theme/app_theme.dart';

class ServiceCard extends StatelessWidget {
  final ServiceState state;
  final ProcessSupervisor supervisor;

  const ServiceCard({
    super.key,
    required this.state,
    required this.supervisor,
  });

  IconData _getServiceIcon(ServiceId id) {
    switch (id) {
      case ServiceId.rabbitmq:
        return Icons.sync_alt_rounded;
      case ServiceId.besu:
        return Icons.link_rounded;
      case ServiceId.dashboardBackend:
        return Icons.hub_outlined;
      case ServiceId.consumer:
        return Icons.security_rounded;
      case ServiceId.xflServer:
        return Icons.psychology_outlined;
      case ServiceId.grafana:
        return Icons.analytics_outlined;
    }
  }

  Color _getStatusColor(ServiceStatus status) {
    switch (status) {
      case ServiceStatus.running:
        return AppTheme.statusGreen;
      case ServiceStatus.starting:
        return AppTheme.statusAmber;
      case ServiceStatus.stopping:
        return AppTheme.statusAmber;
      case ServiceStatus.crashed:
        return AppTheme.statusRed;
      case ServiceStatus.warning:
        return AppTheme.statusAmber;
      case ServiceStatus.stopped:
        return AppTheme.textMuted;
    }
  }

  String _getStatusText(ServiceStatus status) {
    switch (status) {
      case ServiceStatus.running:
        return 'RUNNING';
      case ServiceStatus.starting:
        return 'STARTING...';
      case ServiceStatus.stopping:
        return 'STOPPING...';
      case ServiceStatus.crashed:
        return 'CRASHED';
      case ServiceStatus.warning:
        return 'WARNING';
      case ServiceStatus.stopped:
        return 'STOPPED';
    }
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  @override
  Widget build(BuildContext context) {
    final config = state.config;
    final statusColor = _getStatusColor(state.status);
    final statusText = _getStatusText(state.status);
    final isRunning = state.status == ServiceStatus.running;
    final isBusy = state.status == ServiceStatus.starting ||
        state.status == ServiceStatus.stopping;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: state.status == ServiceStatus.crashed
              ? AppTheme.statusRed.withOpacity(0.6)
              : (isRunning ? AppTheme.statusGreen.withOpacity(0.3) : AppTheme.border),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header: Icon, Title, and Status Pill ──
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  _getServiceIcon(config.id),
                  color: statusColor,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      config.displayName,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      config.type.name.toUpperCase(),
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.6,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              // Status Pill
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: statusColor.withOpacity(0.3)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: statusColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      statusText,
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // ── Description ──
          Text(
            config.description,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 11,
              color: AppTheme.textSecondary,
              height: 1.3,
            ),
          ),

          const Spacer(),

          // ── Metrics Row: Port, PID, and Uptime ──
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: AppTheme.surfaceElevated.withOpacity(0.5),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              children: [
                if (config.primaryPort != null) ...[
                  Icon(
                    Icons.lan_outlined,
                    size: 13,
                    color: state.isPortOpen
                        ? AppTheme.statusCyan
                        : AppTheme.textMuted,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Port ${config.primaryPort}',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: state.isPortOpen
                          ? AppTheme.statusCyan
                          : AppTheme.textMuted,
                    ),
                  ),
                  if (state.portLatencyMs != null) ...[
                    Text(
                      ' (${state.portLatencyMs}ms)',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ],
                  const SizedBox(width: 12),
                ],
                if (state.pid != null) ...[
                  const Icon(Icons.memory_outlined,
                      size: 13, color: AppTheme.textSecondary),
                  const SizedBox(width: 4),
                  Text(
                    'PID: ${state.pid}',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(width: 12),
                ],
                const Spacer(),
                if (isRunning) ...[
                  const Icon(Icons.timer_outlined,
                      size: 13, color: AppTheme.textSecondary),
                  const SizedBox(width: 4),
                  Text(
                    state.uptimeFormatted,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 12),

          // ── Action Controls Bar ──
          Row(
            children: [
              // Start / Stop Toggle
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: isBusy
                      ? null
                      : () {
                          if (isRunning) {
                            supervisor.stopService(config.id);
                          } else {
                            supervisor.startService(config.id);
                          }
                        },
                  icon: Icon(
                    isRunning ? Icons.stop_rounded : Icons.play_arrow_rounded,
                    size: 16,
                  ),
                  label: Text(isRunning ? 'Stop' : 'Start'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isRunning
                        ? AppTheme.statusRed.withOpacity(0.15)
                        : AppTheme.statusGreen.withOpacity(0.15),
                    foregroundColor:
                        isRunning ? AppTheme.statusRed : AppTheme.statusGreen,
                    side: BorderSide(
                      color: isRunning
                          ? AppTheme.statusRed.withOpacity(0.4)
                          : AppTheme.statusGreen.withOpacity(0.4),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 8),
                  ),
                ),
              ),

              const SizedBox(width: 8),

              // Restart Button
              IconButton(
                tooltip: 'Restart Service',
                onPressed: isBusy
                    ? null
                    : () => supervisor.restartService(config.id),
                icon: const Icon(Icons.refresh_rounded, size: 18),
                style: IconButton.styleFrom(
                  backgroundColor: AppTheme.surfaceElevated,
                  foregroundColor: AppTheme.textSecondary,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                    side: const BorderSide(color: AppTheme.border),
                  ),
                ),
              ),

              // Web UI Link (if applicable)
              if (config.webUiUrl != null) ...[
                const SizedBox(width: 8),
                IconButton(
                  tooltip: 'Open in Browser (${config.webUiUrl})',
                  onPressed: () => _launchUrl(config.webUiUrl!),
                  icon: const Icon(Icons.open_in_new_rounded, size: 18),
                  style: IconButton.styleFrom(
                    backgroundColor: AppTheme.surfaceElevated,
                    foregroundColor: AppTheme.statusCyan,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                      side: const BorderSide(color: AppTheme.border),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
