import 'dart:io';
import 'package:path/path.dart' as p;

/// Handles OS-specific behaviors across Windows and Linux Desktop
class PlatformAdapter {
  static bool get isWindows => Platform.isWindows;
  static bool get isLinux => Platform.isLinux;

  /// Dynamically locates the IoT_data_sharing repository root
  static Directory findRepoRoot() {
    var current = Directory.current;

    // A packaged desktop executable can be several directories below the repository root.
    while (true) {
      if (File(p.join(current.path, 'server.py')).existsSync() &&
          Directory(p.join(current.path, 'dashboard-frontend')).existsSync()) {
        return current;
      }

      final parent = current.parent;
      if (parent.path == current.path) break;
      current = parent;
    }

    return Directory.current;
  }

  /// Resolves the Python executable path within the virtualenv or system
  static String getPythonExecutable(Directory repoRoot) {
    if (isWindows) {
      final venvPython = File(p.join(repoRoot.path, 'venv', 'Scripts', 'python.exe'));
      if (venvPython.existsSync()) return venvPython.path;
      return 'python';
    } else {
      final venvPython = File(p.join(repoRoot.path, 'venv', 'bin', 'python'));
      if (venvPython.existsSync()) return venvPython.path;
      return 'python3';
    }
  }

  /// Resolves the Node.js executable
  static String getNodeExecutable() {
    return 'node';
  }

  /// Resolves the NPM executable
  static String getNpmExecutable() {
    return isWindows ? 'npm.cmd' : 'npm';
  }

  /// Resolves the Docker command (prefers 'docker compose')
  static String getDockerExecutable() {
    return 'docker';
  }

  /// Forcefully terminates a process and all of its child processes
  static Future<void> killProcessTree(int pid) async {
    try {
      if (isWindows) {
        await Process.run('taskkill', ['/PID', pid.toString(), '/T', '/F']);
      } else {
        // On Linux, terminate process group
        try {
          await Process.run('kill', ['-TERM', '-$pid']);
        } catch (_) {
          Process.killPid(pid, ProcessSignal.sigkill);
        }
      }
    } catch (e) {
      // Fallback
      Process.killPid(pid, ProcessSignal.sigkill);
    }
  }

  /// Generates a shell wrapper if needed
  static List<String> wrapInShell(String command) {
    if (isWindows) {
      return ['cmd.exe', '/c', command];
    } else {
      return ['/bin/bash', '-c', command];
    }
  }
}
