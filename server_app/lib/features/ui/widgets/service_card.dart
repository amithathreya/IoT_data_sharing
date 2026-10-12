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
        return Icons.hub_rounded;
      case ServiceId.dashboardBackend:
        return Icons.developer_board_rounded;
      case ServiceId.dashboardFrontend:
        return Icons.dashboard_customize_rounded;
      case ServiceId.consumer:
        return Icons.shield_outlined;
      case ServiceId.audioConsumer:
        return Icons.headphones_rounded;
      case ServiceId.xflServer:
        return Icons.settings_suggest_rounded;
      case ServiceId.grafana:
        return Icons.bar_chart_rounded;
    }
  }

  Color _getServiceBrandColor(ServiceId id) {
    switch (id) {
      case ServiceId.rabbitmq:
        return const Color(0xFFEA580C);
      case ServiceId.besu:
        return const Color(0xFF2563EB);
      case ServiceId.dashboardBackend:
        return const Color(0xFF16A34A);
      case ServiceId.dashboardFrontend:
        return const Color(0xFF0D9488);
      case ServiceId.consumer:
        return const Color(0xFF2563EB);
      case ServiceId.audioConsumer:
        return const Color(0xFF6366F1);
      case ServiceId.xflServer:
        return const Color(0xFF9333EA);
      case ServiceId.grafana:
        return const Color(0xFF3B82F6);
    }
  }

  Color _getStatusDotColor(ServiceStatus status) {
    switch (status) {
      case ServiceStatus.running:
        return AppTheme.statusGreen;
      case ServiceStatus.starting:
      case ServiceStatus.stopping:
      case ServiceStatus.warning:
        return AppTheme.statusAmber;
      case ServiceStatus.crashed:
        return AppTheme.statusRed;
      case ServiceStatus.stopped:
        return const Color(0xFF64748B);
    }
  }

  Color _getStatusBgColor(ServiceStatus status) {
    switch (status) {
      case ServiceStatus.running:
        return AppTheme.statusGreenLight;
      case ServiceStatus.starting:
      case ServiceStatus.stopping:
      case ServiceStatus.warning:
        return AppTheme.statusAmberLight;
      case ServiceStatus.crashed:
        return AppTheme.statusRedLight;
      case ServiceStatus.stopped:
        return const Color(0xFFF1F5F9);
    }
  }

  Color _getStatusBorderColor(ServiceStatus status) {
    switch (status) {
      case ServiceStatus.running:
        return AppTheme.statusGreenBorder;
      case ServiceStatus.starting:
      case ServiceStatus.stopping:
      case ServiceStatus.warning:
        return AppTheme.statusAmberBorder;
      case ServiceStatus.crashed:
        return AppTheme.statusRedBorder;
      case ServiceStatus.stopped:
        return AppTheme.border;
    }
  }

  String _getStatusText(ServiceStatus status) {
    switch (status) {
      case ServiceStatus.running:
        return 'RUNNING';
      case ServiceStatus.starting:
        return 'STARTING';
      case ServiceStatus.stopping:
        return 'STOPPING';
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
    final dotColor = _getStatusDotColor(state.status);
    final statusBg = _getStatusBgColor(state.status);
    final statusBorder = _getStatusBorderColor(state.status);
    final statusText = _getStatusText(state.status);
    final isRunning = state.status == ServiceStatus.running;
    final isBusy = state.status == ServiceStatus.starting ||
        state.status == ServiceStatus.stopping;
    final brandColor = _getServiceBrandColor(config.id);

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: state.status == ServiceStatus.crashed
              ? AppTheme.statusRedBorder
              : AppTheme.border,
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header: Icon, Title, Type, and Status Pill ──
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: brandColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Icon(
                    _getServiceIcon(config.id),
                    color: brandColor,
                    size: 20,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      config.displayName,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14.5,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      config.type.name.toUpperCase(),
                      style: const TextStyle(
                        fontSize: 10.5,
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
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: statusBorder),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: dotColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      statusText,
                      style: TextStyle(
                        color: dotColor,
                        fontSize: 10.5,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // ── Description ──
          SizedBox(
            height: 36,
            child: Text(
              config.description,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textMuted,
                height: 1.35,
              ),
            ),
          ),

          const Spacer(),

          // ── Metrics Row: Port, Latency, PID, or Empty Placeholder Strip ──
          Container(
            height: 34,
            padding: const EdgeInsets.symmetric(horizontal: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              children: [
                if (config.primaryPort != null) ...[
                  const Icon(
                    Icons.lan_outlined,
                    size: 14,
                    color: AppTheme.textMuted,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'Port ${config.primaryPort}',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11.5,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  if (state.portLatencyMs != null) ...[
                    Text(
                      ' (${state.portLatencyMs}ms)',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10.5,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ],
                ],
                if (state.pid != null) ...[
                  const SizedBox(width: 12),
                  const Icon(Icons.memory_outlined,
                      size: 13, color: AppTheme.textMuted),
                  const SizedBox(width: 4),
                  Text(
                    'PID: ${state.pid}',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
                const Spacer(),
                if (isRunning && state.uptimeFormatted != '--:--') ...[
                  const Icon(Icons.timer_outlined,
                      size: 13, color: AppTheme.textMuted),
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

          const SizedBox(height: 14),

          // ── Action Controls Bar ──
          Row(
            children: [
              // Start / Stop Toggle Button
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
                        ? AppTheme.statusRedLight
                        : AppTheme.primaryBlueLight,
                    foregroundColor:
                        isRunning ? AppTheme.statusRed : AppTheme.primaryBlue,
                    elevation: 0,
                    side: BorderSide(
                      color: isRunning
                          ? AppTheme.statusRedBorder
                          : AppTheme.primaryBlueBorder,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    textStyle: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),

              const SizedBox(width: 8),

              // Restart Icon Button
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.border),
                ),
                child: IconButton(
                  tooltip: 'Restart Service',
                  padding: EdgeInsets.zero,
                  onPressed: isBusy
                      ? null
                      : () => supervisor.restartService(config.id),
                  icon: const Icon(Icons.refresh_rounded, size: 18, color: Color(0xFF475569)),
                ),
              ),

              // Web UI Link Button (if applicable)
              if (config.webUiUrl != null) ...[
                const SizedBox(width: 8),
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: IconButton(
                    tooltip: 'Open in Browser (${config.webUiUrl})',
                    padding: EdgeInsets.zero,
                    onPressed: () => _launchUrl(config.webUiUrl!),
                    icon: const Icon(Icons.open_in_new_rounded, size: 18, color: AppTheme.primaryBlue),
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
