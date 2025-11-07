// lib/screens/accounts_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../models/account.dart';

class AccountsScreen extends StatefulWidget {
  const AccountsScreen({super.key});

  @override
  _AccountsScreenState createState() => _AccountsScreenState();
}

class _AccountsScreenState extends State<AccountsScreen> {
  late Future<List<BankWithAccounts>> _accountsFuture;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _loadAccounts();
  }

  void _loadAccounts() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    if (authProvider.isAuthenticated) {
      _accountsFuture = _apiService.getAccounts(
        authProvider.token!,
        authProvider.userId!,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Мои счета'),
        actions: [
          IconButton(
            icon: const Icon(Icons.link),
            tooltip: 'Мои подключения',
            onPressed: () {
              Navigator.of(context).pushNamed('/connections');
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Выход',
            onPressed: () {
              Provider.of<AuthProvider>(context, listen: false).logout();
            },
          ),
        ],
      ),
      body: FutureBuilder<List<BankWithAccounts>>(
        future: _accountsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          } else if (snapshot.hasError) {
            return Center(
              child: Text('Ошибка загрузки счетов: ${snapshot.error}'),
            );
          } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text('Счетов не найдено.'));
          }

          final banks = snapshot.data!;
          return ListView.builder(
            itemCount: banks.length,
            itemBuilder: (ctx, index) {
              final bank = banks[index];
              return Card(
                margin: const EdgeInsets.all(8.0),
                child: ExpansionTile(
                  title: Text(
                    bank.name.toUpperCase(),
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                    ),
                  ),
                  children: bank.accounts.map((account) {
                    final balance = account.balances.isNotEmpty
                        ? account.balances.first
                        : null;
                    return ListTile(
                      title: Text(account.nickname),
                      subtitle: Text('ID: ${account.apiAccountId}'),
                      trailing: balance != null
                          ? Text(
                              '${balance.amount} ${balance.currency}',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                              ),
                            )
                          : const Text('Нет данных о балансе'),
                    );
                  }).toList(),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
