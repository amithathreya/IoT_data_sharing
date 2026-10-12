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
        return const Color(0xFFEA580C);
      case ServiceId.besu:
        return const Color(0xFF2563EB);
      case ServiceId.dashboardBackend:
        return const Color(0xFF16A34A);
      case ServiceId.dashboardFrontend:
        return const Color(0xFF0D9488);
      case ServiceId.consumer:
        return const Color(0xFF0284C7);
      case ServiceId.audioConsumer:
        return const Color(0xFF6366F1);
      case ServiceId.xflServer:
        return const Color(0xFF9333EA);
      case ServiceId.grafana:
        return const Color(0xFF3B82F6);
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
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ── Header Bar ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              children: [
                const Icon(
                  Icons.article_outlined,
                  size: 20,
                  color: AppTheme.primaryBlue,
                ),
                const SizedBox(width: 8),
                const Text(
                  'LIVE UNIFIED LOG STREAM',
                  style: TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                    letterSpacing: 0.5,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  '(${logs.length} lines)',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textMuted,
                  ),
                ),

                const Spacer(),

                // Search Box
                SizedBox(
                  width: 200,
                  height: 34,
                  child: TextField(
                    controller: _searchController,
                    onChanged: (val) => widget.logAggregator.setSearchQuery(val),
                    style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
                    decoration: InputDecoration(
                      hintText: 'Search logs...',
                      hintStyle: const TextStyle(fontSize: 12, color: AppTheme.textSubtle),
                      prefixIcon: const Icon(Icons.search, size: 16, color: AppTheme.textMuted),
                      prefixIconConstraints: const BoxConstraints(minWidth: 32),
                      contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 8),
                      filled: true,
                      fillColor: Colors.white,
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: AppTheme.borderSubtle),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: AppTheme.primaryBlue),
                      ),
                    ),
                  ),
                ),

                const SizedBox(width: 10),

                // Errors Only Filter
                OutlinedButton(
                  onPressed: () => widget.logAggregator.setErrorsOnly(!errorsOnly),
                  style: OutlinedButton.styleFrom(
                    backgroundColor: errorsOnly ? AppTheme.statusRedLight : Colors.white,
                    side: BorderSide(
                      color: errorsOnly ? AppTheme.statusRedBorder : AppTheme.borderSubtle,
                    ),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  child: Text(
                    'Errors Only',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: errorsOnly ? FontWeight.bold : FontWeight.w500,
                      color: errorsOnly ? AppTheme.statusRed : AppTheme.textSecondary,
                    ),
                  ),
                ),

                const SizedBox(width: 8),

                // Auto Scroll Toggle Button
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppTheme.borderSubtle),
                  ),
                  child: IconButton(
                    tooltip: _autoScroll ? 'Disable Auto-Scroll' : 'Enable Auto-Scroll',
                    padding: EdgeInsets.zero,
                    icon: Icon(
                      _autoScroll ? Icons.file_download_outlined : Icons.pause_circle_outline,
                      size: 18,
                      color: _autoScroll ? AppTheme.primaryBlue : AppTheme.textMuted,
                    ),
                    onPressed: () => setState(() => _autoScroll = !_autoScroll),
                  ),
                ),

                const SizedBox(width: 8),

                // Clear Logs Button
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppTheme.borderSubtle),
                  ),
                  child: IconButton(
                    tooltip: 'Clear Output',
                    padding: EdgeInsets.zero,
                    icon: const Icon(
                      Icons.delete_outline,
                      size: 18,
                      color: AppTheme.textMuted,
                    ),
                    onPressed: () => widget.logAggregator.clearLogs(),
                  ),
                ),
              ],
            ),
          ),

          const Divider(color: AppTheme.border, height: 1),

          // ── Service Filter Tabs ──
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: const BoxDecoration(
              color: Colors.white,
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

          // ── Terminal Console Output View ──
          Padding(
            padding: const EdgeInsets.all(12),
            child: Container(
              height: 260,
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              child: logs.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: const Color(0xFFCBD5E1)),
                            ),
                            child: const Text(
                              '>..',
                              style: TextStyle(
                                fontFamily: 'Consolas',
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF64748B),
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            'Waiting for process outputs... (Start services above to stream output)',
                            style: TextStyle(
                              fontSize: 12.5,
                              color: Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(10),
                      itemCount: logs.length,
                      itemBuilder: (context, index) {
                        final entry = logs[index];
                        return _buildLogLine(entry);
                      },
                    ),
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
        borderRadius: BorderRadius.circular(6),
        onTap: () => widget.logAggregator.setFilter(id),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primaryBlueLight : Colors.transparent,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(
              color: isSelected ? AppTheme.primaryBlueBorder : Colors.transparent,
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
              color: isSelected ? AppTheme.primaryBlue : AppTheme.textMuted,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLogLine(LogEntry entry) {
    final tagColor = _getServiceTagColor(entry.serviceId);
    Color textColor = const Color(0xFF1E293B);
    if (entry.isError) {
      textColor = AppTheme.statusRed;
    } else if (entry.isWarning) {
      textColor = AppTheme.statusAmber;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: SelectableText.rich(
        TextSpan(
          style: const TextStyle(
            fontFamily: 'Consolas',
            fontSize: 12,
            height: 1.35,
          ),
          children: [
            // Timestamp
            TextSpan(
              text: '[${entry.timeFormatted}] ',
              style: const TextStyle(color: Color(0xFF94A3B8)),
            ),
            // Service Tag
            TextSpan(
              text: '[${entry.serviceId.name}] ',
              style: TextStyle(
                color: tagColor,
                fontWeight: FontWeight.bold,
              ),
            ),
            // Level indicator
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
            // Log Content
            TextSpan(
              text: entry.text,
              style: TextStyle(
                color: textColor,
                fontWeight: entry.isError ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
