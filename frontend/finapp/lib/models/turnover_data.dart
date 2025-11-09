// lib/models/turnover_data.dart

class TurnoverData {
  final double totalCredit;
  final double totalDebit;
  final String currency;

  TurnoverData({
    required this.totalCredit,
    required this.totalDebit,
    required this.currency,
  });

  factory TurnoverData.fromJson(Map<String, dynamic> json) {
    return TurnoverData(
      totalCredit: double.tryParse(json['total_credit'].toString()) ?? 0.0,
      totalDebit: double.tryParse(json['total_debit'].toString()) ?? 0.0,
      currency: json['currency'] ?? 'N/A',
    );
  }
}