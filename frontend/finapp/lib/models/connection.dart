// lib/models/connection.dart

class Connection {
  final int id;
  final String bankName;
  final String bankClientId;
  final String status;
  final String? consentId;

  Connection({
    required this.id,
    required this.bankName,
    required this.bankClientId,
    required this.status,
    this.consentId,
  });

  factory Connection.fromJson(Map<String, dynamic> json) {
    return Connection(
      id: json['id'],
      bankName: json['bank_name'],
      bankClientId: json['bank_client_id'],
      status: json['status'],
      consentId: json['consent_id'],
    );
  }
}
