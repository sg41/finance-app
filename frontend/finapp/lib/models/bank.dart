// lib/models/bank.dart
class Bank {
  final int id;
  final String name;
  final String? iconUrl;

  Bank({required this.id, required this.name, this.iconUrl});

  factory Bank.fromJson(Map<String, dynamic> json) {
    return Bank(id: json['id'], name: json['name'], iconUrl: json['icon_url']);
  }
}
