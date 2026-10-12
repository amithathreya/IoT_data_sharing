import 'package:flutter/material.dart';

class AppTheme {
  // Background & Surface (matching clean enterprise supervisor layout in provided image)
  static const Color background = Color(0xFF242424);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceElevated = Color(0xFFF1F5F9);
  static const Color border = Color(0xFFE2E8F0);
  static const Color borderSubtle = Color(0xFFCBD5E1);

  // Brand / Action Colors
  static const Color primaryBlue = Color(0xFF2563EB);
  static const Color primaryBlueHover = Color(0xFF1D4ED8);
  static const Color primaryBlueLight = Color(0xFFEFF6FF);
  static const Color primaryBlueBorder = Color(0xFFBFDBFE);

  // Status Colors
  static const Color statusGreen = Color(0xFF10B981);
  static const Color statusGreenLight = Color(0xFFECFDF5);
  static const Color statusGreenBorder = Color(0xFFA7F3D0);

  static const Color statusAmber = Color(0xFFD97706);
  static const Color statusAmberLight = Color(0xFFFFFBEB);
  static const Color statusAmberBorder = Color(0xFFFDE68A);

  static const Color statusRed = Color(0xFFDC2626);
  static const Color statusRedLight = Color(0xFFFEE2E2);
  static const Color statusRedBorder = Color(0xFFFECACA);

  static const Color statusPurple = Color(0xFF9333EA);
  static const Color statusPurpleLight = Color(0xFFFAF5FF);

  static const Color statusCyan = Color(0xFF0284C7);
  static const Color statusIndigo = Color(0xFF6366F1);

  // Text Colors
  static const Color textPrimary = Color(0xFF0F172A);
  static const Color textSecondary = Color(0xFF475569);
  static const Color textMuted = Color(0xFF64748B);
  static const Color textSubtle = Color(0xFF94A3B8);

  static ThemeData get lightTheme {
    return ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: background,
      primaryColor: primaryBlue,
      cardColor: surface,
      dividerColor: border,
      fontFamily: 'Segoe UI',
      colorScheme: const ColorScheme.light(
        primary: primaryBlue,
        secondary: statusGreen,
        surface: surface,
        error: statusRed,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: border, width: 1),
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryBlue,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: borderSubtle),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
    );
  }

  // Backward compatibility alias
  static ThemeData get darkTheme => lightTheme;
}
