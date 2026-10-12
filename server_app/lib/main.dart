import 'package:flutter/material.dart';
import 'core/platform/platform_adapter.dart';
import 'core/theme/app_theme.dart';
import 'features/ui/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final repoRoot = PlatformAdapter.findRepoRoot();

  runApp(ServerSupervisorApp(repoRoot: repoRoot));
}

class ServerSupervisorApp extends StatelessWidget {
  final dynamic repoRoot;
  final bool enableWatchdog;

  const ServerSupervisorApp({
    super.key,
    required this.repoRoot,
    this.enableWatchdog = true,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PQC Security Server Supervisor',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: HomeScreen(
        repoRoot: repoRoot,
        enableWatchdog: enableWatchdog,
      ),
    );
  }
}
