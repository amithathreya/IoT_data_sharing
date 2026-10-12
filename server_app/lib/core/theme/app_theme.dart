import 'package:flutter/material.dart';

class AppTheme {
  // Background & Surface
  static const Color background = Color(0xFF11161C);
  static const Color surface = Color(0xFF1A212B);
  static const Color surfaceElevated = Color(0xFF232D3A);
  static const Color border = Color(0xFF344050);
  static const Color borderSubtle = Color(0xFF455367);

  // Brand / Action Colors
  static const Color primaryBlue = Color(0xFF63A5FF);
  static const Color primaryBlueHover = Color(0xFF3E8EFF);
  static const Color primaryBlueLight = Color(0xFF1E2F47);
  static const Color primaryBlueBorder = Color(0xFF3A4F6D);

  // Status Colors
  static const Color statusGreen = Color(0xFF43C990);
  static const Color statusGreenLight = Color(0xFF1B3329);
  static const Color statusGreenBorder = Color(0xFF2F5B49);

  static const Color statusAmber = Color(0xFFF2B35B);
  static const Color statusAmberLight = Color(0xFF3A2F1F);
  static const Color statusAmberBorder = Color(0xFF5C4A2F);

  static const Color statusRed = Color(0xFFFF7A7A);
  static const Color statusRedLight = Color(0xFF3E2427);
  static const Color statusRedBorder = Color(0xFF6A3A3F);

  static const Color statusPurple = Color(0xFFC18BFF);
  static const Color statusPurpleLight = Color(0xFF352945);

  static const Color statusCyan = Color(0xFF4ABED9);
  static const Color statusIndigo = Color(0xFF96A0FF);

  // Text Colors
  static const Color textPrimary = Color(0xFFE9EEF5);
  static const Color textSecondary = Color(0xFFB7C2CF);
  static const Color textMuted = Color(0xFF8D9AAD);
  static const Color textSubtle = Color(0xFF6D7B90);

  static ThemeData get lightTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      primaryColor: primaryBlue,
      cardColor: surface,
      dividerColor: border,
      fontFamily: 'Segoe UI',
      colorScheme: const ColorScheme.dark(
        primary: primaryBlue,
        secondary: statusGreen,
        surface: surface,
        error: statusRed,
        onPrimary: Colors.white,
        onSecondary: Color(0xFF04150C),
        onSurface: textPrimary,
        onError: Color(0xFF2B0000),
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
          disabledBackgroundColor: surfaceElevated,
          disabledForegroundColor: textSubtle,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textSecondary,
          backgroundColor: surface,
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
