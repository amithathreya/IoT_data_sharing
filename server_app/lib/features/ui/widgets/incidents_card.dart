import 'package:flutter/material.dart';
import '../../supervisor/services/process_supervisor.dart';
import '../../../core/theme/app_theme.dart';

class IncidentsCard extends StatelessWidget {
  final ProcessSupervisor supervisor;

  const IncidentsCard({
    super.key,
    required this.supervisor,
  });

  @override
  Widget build(BuildContext context) {
    final activeIncidents =
        supervisor.incidents.where((i) => !i.isResolved).toList();

    if (activeIncidents.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.only(left: 20, right: 20, top: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.statusRed.withOpacity(0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.statusRed.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: AppTheme.statusRed.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.report_problem_rounded,
                  color: AppTheme.statusRed,
                  size: 18,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                'ACTIVE INCIDENTS & CRASH DIAGNOSTICS (${activeIncidents.length})',
                style: const TextStyle(
                  color: AppTheme.statusRed,
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                  letterSpacing: 0.8,
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () => supervisor.clearAllIncidents(),
                child: const Text(
                  'Dismiss All',
                  style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: activeIncidents.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final incident = activeIncidents[index];
              return Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.statusRed.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        incident.serviceId?.name.toUpperCase() ?? 'SYSTEM',
                        style: const TextStyle(
                          color: AppTheme.statusRed,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                incident.title,
                                style: const TextStyle(
                                  color: AppTheme.textPrimary,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                ),
                              ),
                              const Spacer(),
                              Text(
                                incident.timeFormatted,
                                style: const TextStyle(
                                  color: AppTheme.textMuted,
                                  fontSize: 11,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ),
                          if (incident.details.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              incident.details,
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
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
                    const SizedBox(width: 12),
                    if (incident.serviceId != null)
                      ElevatedButton.icon(
                        onPressed: () {
                          supervisor.restartService(incident.serviceId!);
                          supervisor.resolveIncident(incident.id);
                        },
                        icon: const Icon(Icons.refresh, size: 14),
                        label: const Text('Restart'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor:
                              AppTheme.statusAmber.withOpacity(0.18),
                          foregroundColor: AppTheme.statusAmber,
                          side: BorderSide(
                              color: AppTheme.statusAmber.withOpacity(0.4)),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 6),
                          textStyle: const TextStyle(fontSize: 11),
                        ),
                      ),
                    IconButton(
                      tooltip: 'Mark Resolved',
                      icon: const Icon(Icons.check,
                          size: 16, color: AppTheme.textMuted),
                      onPressed: () => supervisor.resolveIncident(incident.id),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}
