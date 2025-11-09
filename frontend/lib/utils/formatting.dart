// frontend/finapp/lib/utils/formatting.dart

import 'package:intl/intl.dart';

/// Возвращает общепринятый символ валюты по ее коду ISO 4217.
String getCurrencySymbol(String? currencyCode) {
  switch (currencyCode?.toUpperCase()) {
    case 'RUB':
      return '₽';
    case 'USD':
      return '\$';
    case 'EUR':
      return '€';
    default:
      // Если символ не найден, возвращаем сам код.
      return currencyCode ?? '';
  }
}

extension NumberFormatting on num {
  /// Форматирует число как валюту с разделителями разрядов (пробелами) и символом.
  ///
  /// Локаль 'ru_RU' используется для формата "1 234 567,89 ₽".
  ///
  /// Пример:
  /// ```dart
  /// 15200.7.toFormattedCurrency('RUB') // "15 200,70 ₽"
  /// 1000000.toFormattedCurrency('USD') // "1 000 000,00 $"
  /// ```
  String toFormattedCurrency(String currencyCode) {
    final symbol = getCurrencySymbol(currencyCode);
    
    // Форматтер для локали 'ru_RU' использует пробел как разделитель тысяч
    // и запятую как десятичный разделитель.
    final formatter = NumberFormat.currency(
      locale: 'ru_RU',
      symbol: symbol,
      decimalDigits: 2, // Всегда показывать 2 знака после запятой.
    );

    return formatter.format(this);
  }
}