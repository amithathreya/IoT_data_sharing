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
    final bgColor = isCritical ? AppTheme.statusRedLight : AppTheme.statusAmberLight;
    final borderColor = isCritical ? AppTheme.statusRedBorder : AppTheme.statusAmberBorder;
    final titleColor = isCritical ? const Color(0xFF991B1B) : const Color(0xFF92400E);
    final descColor = isCritical ? AppTheme.statusRed : const Color(0xFFB45309);
    final iconColor = isCritical ? AppTheme.statusRed : AppTheme.statusAmber;

    return Container(
      margin: const EdgeInsets.only(left: 20, right: 20, top: 16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borderColor, width: 1),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(
            isCritical ? Icons.error_outline_rounded : Icons.warning_amber_rounded,
            color: iconColor,
            size: 26,
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
                    color: titleColor,
                    fontWeight: FontWeight.bold,
                    fontSize: 13.5,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  unsatisfiedItems.map((i) => '${i.name}: ${i.errorOrWarning}').join(' • '),
                  style: TextStyle(
                    color: descColor,
                    fontSize: 12,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          // If node_modules is unsatisfied, provide quick install button
          if (unsatisfiedItems.any((i) => i.id == 'node_modules')) ...[
            ElevatedButton.icon(
              onPressed: isFixingNodeDeps ? null : onInstallNodeDeps,
              icon: isFixingNodeDeps
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.download_rounded, size: 14),
              label: Text(isFixingNodeDeps ? 'Installing...' : 'Run npm install'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryBlue,
                foregroundColor: Colors.white,
                elevation: 0,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
              ),
            ),
            const SizedBox(width: 8),
          ],
          IconButton(
            tooltip: 'Re-run Preflight Audit',
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh, size: 20, color: Color(0xFF475569)),
          ),
        ],
      ),
    );
  }
}
