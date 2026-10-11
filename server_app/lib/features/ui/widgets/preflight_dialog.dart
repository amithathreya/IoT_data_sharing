import 'package:flutter/material.dart';
import '../../../core/services/preflight_service.dart';
import '../../../core/theme/app_theme.dart';

class PreflightDialog extends StatelessWidget {
  final PreflightReport report;
  final VoidCallback onRefresh;
  final VoidCallback onInstallNodeDeps;
  final bool isFixingNodeDeps;

  const PreflightDialog({
    super.key,
    required this.report,
    required this.onRefresh,
    required this.onInstallNodeDeps,
    this.isFixingNodeDeps = false,
  });

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppTheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppTheme.border),
      ),
      child: Container(
        width: 600,
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.fact_check_outlined,
                    color: AppTheme.statusCyan, size: 22),
                const SizedBox(width: 10),
                const Text(
                  'ENVIRONMENT PREFLIGHT AUDIT',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: AppTheme.textPrimary,
                    letterSpacing: 0.8,
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Audited at ${report.timestamp.toLocal().toString().split('.').first}',
              style: const TextStyle(color: AppTheme.textMuted, fontSize: 11),
            ),
            const SizedBox(height: 16),
            const Divider(color: AppTheme.border, height: 1),
            const SizedBox(height: 16),
            Flexible(
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: report.items.length,
                separatorBuilder: (context, index) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final item = report.items[index];
                  final isOk = item.isSatisfied;
                  final statusColor =
                      isOk ? AppTheme.statusGreen : (item.isCritical ? AppTheme.statusRed : AppTheme.statusAmber);

                  return Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceElevated.withOpacity(0.5),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: statusColor.withOpacity(0.3)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          isOk ? Icons.check_circle_outline_rounded : Icons.cancel_outlined,
                          color: statusColor,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                item.name,
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                item.description,
                                style: const TextStyle(
                                  color: AppTheme.textSecondary,
                                  fontSize: 11,
                                ),
                              ),
                              if (item.errorOrWarning != null) ...[
                                const SizedBox(height: 6),
                                Text(
                                  item.errorOrWarning!,
                                  style: TextStyle(
                                    color: statusColor,
                                    fontSize: 11,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                        if (!isOk && item.id == 'node_modules') ...[
                          const SizedBox(width: 8),
                          ElevatedButton.icon(
                            onPressed: isFixingNodeDeps ? null : onInstallNodeDeps,
                            icon: const Icon(Icons.download_rounded, size: 14),
                            label: Text(isFixingNodeDeps ? 'Installing...' : 'Install'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.statusCyan.withOpacity(0.2),
                              foregroundColor: AppTheme.statusCyan,
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              textStyle: const TextStyle(fontSize: 11),
                            ),
                          ),
                        ],
                      ],
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton.icon(
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Re-run Audit'),
                ),
                const SizedBox(width: 10),
                ElevatedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Close'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
