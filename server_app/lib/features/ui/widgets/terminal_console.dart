import 'package:flutter/material.dart';
import '../../supervisor/models/service_model.dart';
import '../../terminal/models/log_entry.dart';
import '../../terminal/services/log_aggregator.dart';
import '../../../core/theme/app_theme.dart';

class TerminalConsole extends StatefulWidget {
  final LogAggregator logAggregator;

  const TerminalConsole({
    super.key,
    required this.logAggregator,
  });

  @override
  State<TerminalConsole> createState() => _TerminalConsoleState();
}

class _TerminalConsoleState extends State<TerminalConsole> {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();
  bool _autoScroll = true;

  @override
  void initState() {
    super.initState();
    widget.logAggregator.addListener(_onNewLog);
  }

  @override
  void dispose() {
    widget.logAggregator.removeListener(_onNewLog);
    _scrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _onNewLog() {
    if (_autoScroll && _scrollController.hasClients) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) {
          _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
        }
      });
    }
  }

  Color _getServiceTagColor(ServiceId id) {
    switch (id) {
      case ServiceId.rabbitmq:
        return AppTheme.statusAmber;
      case ServiceId.besu:
        return AppTheme.statusPurple;
      case ServiceId.dashboardBackend:
        return AppTheme.statusCyan;
      case ServiceId.consumer:
        return AppTheme.statusGreen;
      case ServiceId.xflServer:
        return Colors.pinkAccent;
      case ServiceId.grafana:
        return Colors.orangeAccent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final logs = widget.logAggregator.filteredLogs;
    final selectedFilter = widget.logAggregator.selectedFilter;
    final errorsOnly = widget.logAggregator.errorsOnly;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF070A0F),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          // ── Terminal Header & Controls ──
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: AppTheme.surfaceElevated.withOpacity(0.4),
              border: const Border(
                bottom: BorderSide(color: AppTheme.border),
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(10),
                topRight: Radius.circular(10),
              ),
            ),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  const Icon(Icons.terminal_rounded, size: 18, color: AppTheme.statusCyan),
                  const SizedBox(width: 8),
                  const Text(
                    'LIVE UNIFIED LOG STREAM',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      letterSpacing: 0.6,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '(${logs.length} lines)',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppTheme.textMuted,
                    ),
                  ),

                  const SizedBox(width: 24),

                  // Search box
                SizedBox(
                  width: 160,
                  height: 28,
                  child: TextField(
                    controller: _searchController,
                    onChanged: (val) => widget.logAggregator.setSearchQuery(val),
                    style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                    decoration: InputDecoration(
                      hintText: 'Search logs...',
                      hintStyle: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                      prefixIcon: const Icon(Icons.search, size: 14, color: AppTheme.textMuted),
                      prefixIconConstraints: const BoxConstraints(minWidth: 24),
                      contentPadding: EdgeInsets.zero,
                      filled: true,
                      fillColor: AppTheme.surface,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: AppTheme.border),
                      ),
                    ),
                  ),
                ),

                const SizedBox(width: 10),

                // Error Only Filter Chip
                FilterChip(
                  label: const Text('Errors Only'),
                  labelStyle: TextStyle(
                    fontSize: 11,
                    color: errorsOnly ? AppTheme.statusRed : AppTheme.textSecondary,
                    fontWeight: errorsOnly ? FontWeight.bold : FontWeight.normal,
                  ),
                  selected: errorsOnly,
                  selectedColor: AppTheme.statusRed.withOpacity(0.2),
                  checkmarkColor: AppTheme.statusRed,
                  backgroundColor: AppTheme.surface,
                  side: BorderSide(
                    color: errorsOnly
                        ? AppTheme.statusRed.withOpacity(0.5)
                        : AppTheme.border,
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  onSelected: (val) => widget.logAggregator.setErrorsOnly(val),
                ),

                const SizedBox(width: 10),

                // Auto Scroll Toggle
                IconButton(
                  tooltip: _autoScroll ? 'Disable Auto-Scroll' : 'Enable Auto-Scroll',
                  icon: Icon(
                    _autoScroll ? Icons.vertical_align_bottom : Icons.pause_circle_outline,
                    size: 16,
                    color: _autoScroll ? AppTheme.statusCyan : AppTheme.textMuted,
                  ),
                  onPressed: () => setState(() => _autoScroll = !_autoScroll),
                ),

                // Clear button
                IconButton(
                  tooltip: 'Clear Terminal Output',
                  icon: const Icon(Icons.delete_sweep_outlined, size: 16, color: AppTheme.textMuted),
                  onPressed: () => widget.logAggregator.clearLogs(),
                ),
              ],
            ),
          ),
        ),

          // ── Service Filter Tabs ──
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: const BoxDecoration(
              color: Color(0xFF0C1017),
              border: Border(bottom: BorderSide(color: AppTheme.border)),
            ),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _buildTab('ALL', null, selectedFilter),
                  ...ServiceConfig.allServices.map((cfg) {
                    return _buildTab(cfg.displayName, cfg.id, selectedFilter);
                  }),
                ],
              ),
            ),
          ),

          // ── Streaming Terminal Logs ──
          Container(
            height: 280,
            padding: const EdgeInsets.all(12),
            child: logs.isEmpty
                ? const Center(
                    child: Text(
                      'Waiting for process outputs... (Start services above to stream output)',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: AppTheme.textMuted,
                        fontSize: 12,
                      ),
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    itemCount: logs.length,
                    itemBuilder: (context, index) {
                      final entry = logs[index];
                      return _buildLogLine(entry);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTab(String label, ServiceId? id, ServiceId? activeId) {
    final isSelected = activeId == id;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(4),
        onTap: () => widget.logAggregator.setFilter(id),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.surfaceElevated : Colors.transparent,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(
              color: isSelected ? AppTheme.statusCyan.withOpacity(0.5) : Colors.transparent,
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 10,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              color: isSelected ? AppTheme.statusCyan : AppTheme.textMuted,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLogLine(LogEntry entry) {
    final tagColor = _getServiceTagColor(entry.serviceId);
    Color textColor = AppTheme.textPrimary;
    if (entry.isError) {
      textColor = AppTheme.statusRed;
    } else if (entry.isWarning) {
      textColor = AppTheme.statusAmber;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1.5),
      child: SelectableText.rich(
        TextSpan(
          style: const TextStyle(
            fontFamily: 'Consolas',
            fontSize: 11.5,
            height: 1.3,
          ),
          children: [
            // Timestamp
            TextSpan(
              text: '[${entry.timeFormatted}] ',
              style: const TextStyle(color: Color(0xFF4B5563)),
            ),
            // Service Tag
            TextSpan(
              text: '[${entry.serviceId.name}] ',
              style: TextStyle(
                color: tagColor,
                fontWeight: FontWeight.w600,
              ),
            ),
            // Level if error/warning
            if (entry.isError)
              const TextSpan(
                text: '❌ ',
                style: TextStyle(color: AppTheme.statusRed),
              ),
            if (entry.isWarning)
              const TextSpan(
                text: '⚠️ ',
                style: TextStyle(color: AppTheme.statusAmber),
              ),
            // Content
            TextSpan(
              text: entry.text,
              style: TextStyle(color: textColor),
            ),
          ],
        ),
      ),
    );
  }
}
