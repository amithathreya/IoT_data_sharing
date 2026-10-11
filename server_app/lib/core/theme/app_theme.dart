import 'package:flutter/material.dart';

class AppTheme {
  // Background & Surface
  static const Color background = Color(0xFF090D14);
  static const Color surface = Color(0xFF111827);
  static const Color surfaceElevated = Color(0xFF1F2937);
  static const Color border = Color(0xFF374151);

  // Status Colors
  static const Color statusGreen = Color(0xFF10B981);
  static const Color statusCyan = Color(0xFF06B6D4);
  static const Color statusAmber = Color(0xFFF59E0B);
  static const Color statusRed = Color(0xFFEF4444);
  static const Color statusPurple = Color(0xFFA855F7);

  // Text Colors
  static const Color textPrimary = Color(0xFFF9FAFB);
  static const Color textSecondary = Color(0xFF9CA3AF);
  static const Color textMuted = Color(0xFF6B7280);

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      primaryColor: statusCyan,
      cardColor: surface,
      dividerColor: border,
      fontFamily: 'Segoe UI', // standard on Windows, clean fallback on Linux
      colorScheme: const ColorScheme.dark(
        primary: statusCyan,
        secondary: statusGreen,
        surface: surface,
        error: statusRed,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: border, width: 1),
          borderRadius: BorderRadius.circular(10),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: surfaceElevated,
          foregroundColor: textPrimary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: border),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
    );
  }
}
