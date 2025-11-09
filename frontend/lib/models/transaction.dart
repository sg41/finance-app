// lib/models/transaction.dart

class Transaction {
  final String transactionId;
  final String amount;
  final String currency;
  final String creditDebitIndicator; // 'Credit' or 'Debit'
  final DateTime bookingDateTime;
  final String? transactionInformation;
  final String status;

  Transaction({
    required this.transactionId,
    required this.amount,
    required this.currency,
    required this.creditDebitIndicator,
    required this.bookingDateTime,
    this.transactionInformation,
    required this.status,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      transactionId: json['transactionId'] ?? 'N/A',
      amount: json['amount']['amount'] ?? '0.00',
      currency: json['amount']['currency'] ?? '',
      creditDebitIndicator: json['creditDebitIndicator'] ?? 'N/A',
      bookingDateTime: DateTime.parse(json['bookingDateTime']),
      transactionInformation: json['transactionInformation'],
      status: json['status'] ?? 'Unknown',
    );
  }
}