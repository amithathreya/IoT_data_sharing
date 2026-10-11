import 'package:flutter/material.dart';
import '../../../core/services/preflight_service.dart';
import '../../../core/theme/app_theme.dart';

class PreflightBanner extends StatelessWidget {
  final PreflightReport? report;
  final VoidCallback onRefresh;
  final VoidCallback onInstallNodeDeps;
  final bool isFixingNodeDeps;

  const PreflightBanner({
    super.key,
    required this.report,
    required this.onRefresh,
    required this.onInstallNodeDeps,
    this.isFixingNodeDeps = false,
  });

  @override
  Widget build(BuildContext context) {
    if (report == null || report!.isReady) {
      return const SizedBox.shrink();
    }

    final unsatisfiedItems = report!.items.where((i) => !i.isSatisfied).toList();
    final isCritical = report!.hasCriticalErrors;
    final color = isCritical ? AppTheme.statusRed : AppTheme.statusAmber;

    return Container(
      margin: const EdgeInsets.only(left: 20, right: 20, top: 16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(
            isCritical ? Icons.error_outline_rounded : Icons.warning_amber_rounded,
            color: color,
            size: 24,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isCritical
                      ? 'Preflight Checklist: Critical Requirements Missing'
                      : 'Preflight Checklist: Recommended Configuration Missing',
                  style: TextStyle(
                    color: color,
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  unsatisfiedItems.map((i) => '${i.name}: ${i.errorOrWarning}').join(' • '),
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          // If node_modules is unsatisfied, provide quick install button
          if (unsatisfiedItems.any((i) => i.id == 'node_modules'))
            ElevatedButton.icon(
              onPressed: isFixingNodeDeps ? null : onInstallNodeDeps,
              icon: isFixingNodeDeps
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.statusCyan),
                    )
                  : const Icon(Icons.download_rounded, size: 16),
              label: Text(isFixingNodeDeps ? 'Installing...' : 'Run npm install'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.statusCyan.withOpacity(0.2),
                foregroundColor: AppTheme.statusCyan,
                side: BorderSide(color: AppTheme.statusCyan.withOpacity(0.4)),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
            ),
          const SizedBox(width: 8),
          IconButton(
            tooltip: 'Re-run Preflight Audit',
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh, size: 18, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }
}
