// lib/features/accounts/screens/accounts_screen.dart

import 'package:flutter/material.dart';

class AccountsScreen extends StatelessWidget {
  final Map<String, dynamic> accountsData;

  const AccountsScreen({super.key, required this.accountsData});

  @override
  Widget build(BuildContext context) {
    // Извлекаем список счетов, учитывая вложенную структуру
    final accounts = accountsData['data']['account'] as List<dynamic>;

    return Scaffold(
      appBar: AppBar(title: const Text("Ваши счета")),
      body: ListView.builder(
        itemCount: accounts.length,
        itemBuilder: (context, index) {
          final account = accounts[index];
          // Извлекаем детали счета из еще одного уровня вложенности
          final accountDetails = account['account'][0];
          return Card(
            margin: const EdgeInsets.all(8.0),
            child: ListTile(
              title: Text(accountDetails['name'] ?? 'Нет имени'),
              subtitle: Text("Номер счета: ${accountDetails['identification'] ?? 'Недоступен'}"),
            ),
          );
        },
      ),
    );
  }
}