// frontend/finapp/lib/screens/accounts_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../models/account.dart';
import '../models/connection.dart';
import '../utils/formatting.dart';

class AccountsScreen extends StatefulWidget {
  const AccountsScreen({super.key});

  @override
  _AccountsScreenState createState() => _AccountsScreenState();
}

class _AccountsScreenState extends State<AccountsScreen> {
  final ApiService _apiService = ApiService();
  bool _isRefreshing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _triggerFullRefresh(isInitialLoad: true);
    });
  }

  Future<List<BankWithAccounts>> _fetchAccountsFromDB() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    if (authProvider.isAuthenticated) {
      return _apiService.getAccounts(authProvider.token!, authProvider.userId!);
    }
    return Future.value([]);
  }

  Future<void> _triggerFullRefresh({bool isInitialLoad = false}) async {
    if (_isRefreshing) return;
    setState(() {
      _isRefreshing = true;
    });

    final authProvider = Provider.of<AuthProvider>(context, listen: false);

    try {
      final connections = await _apiService.getConnections(
        authProvider.token!,
        authProvider.userId!,
      );
      final List<Future<void>> allTasks = [];

      for (final conn in connections) {
        if (conn.status == 'active') {
          allTasks.add(
            _apiService.refreshConnection(
              authProvider.token!,
              authProvider.userId!,
              conn.id,
            ),
          );
        } else if (conn.status == 'awaitingauthorization') {
          allTasks.add(
            _apiService.checkConsentStatus(
              authProvider.token!,
              authProvider.userId!,
              conn.id,
            ),
          );
        }
      }

      await Future.wait(allTasks);

      if (!isInitialLoad && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Данные успешно обновлены.'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Ошибка при обновлении: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isRefreshing = false;
        });
      }
    }
  }

  void _navigateToConnections() async {
    final result = await Navigator.of(context).pushNamed('/connections');
    if (result == true && mounted) {
      _triggerFullRefresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    // --- vvv ИЗМЕНЕНИЯ ЗДЕСЬ: Scaffold теперь внутри FutureBuilder vvv ---
    return FutureBuilder<List<BankWithAccounts>>(
      future: _fetchAccountsFromDB(),
      builder: (context, snapshot) {
        // Определяем AppBar до того, как получим данные, чтобы он был на экране всегда
        Widget? appBarTitle;
        Widget body;

        if (snapshot.connectionState == ConnectionState.waiting &&
            !_isRefreshing) {
          body = const Center(child: CircularProgressIndicator());
        } else if (snapshot.hasError) {
          body = Center(
            child: Text('Ошибка загрузки счетов: ${snapshot.error}'),
          );
        } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
          body = const Center(child: Text('Счетов не найдено.'));
        } else {
          // --- ЛОГИКА ПОДСЧЕТА И ПОСТРОЕНИЯ UI ---
          final banks = snapshot.data!;

          // 1. Считаем общую сумму по всем банкам
          final double grandTotal = banks.fold(
            0.0,
            (sum, bank) => sum + bank.totalBalance,
          );

          // 2. Формируем заголовок с общей суммой
          appBarTitle = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Мои счета'),
              Text(
                grandTotal.toFormattedCurrency('RUB'),
                // '${grandTotal.toStringAsFixed(2)} RUB',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.normal,
                ),
              ),
            ],
          );

          // 3. Формируем тело списка
          body = ListView.builder(
            itemCount: banks.length,
            itemBuilder: (ctx, index) {
              final bank = banks[index];
              return Card(
                margin: const EdgeInsets.all(8.0),
                child: ExpansionTile(
                  title: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        bank.name.toUpperCase(),
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                        ),
                      ),
                      Text(
                        bank.totalBalance.toFormattedCurrency('RUB'),
                        // '${bank.totalBalance.toStringAsFixed(2)} RUB',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                    ],
                  ),
                  children: bank.accounts.map((account) {
                    final balance = account.balances.isNotEmpty
                        ? account.balances.first
                        : null;
                    return ListTile(
                      title: Text(account.nickname),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 4.0, bottom: 4.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('ID счета: ${account.apiAccountId}'),
                            Text('ID клиента: ${account.bankClientId}'),
                            if (account.ownerName != null &&
                                account.ownerName!.isNotEmpty)
                              Text('Владелец: ${account.ownerName!}'),
                            if (account.accountType != null &&
                                account.accountType!.isNotEmpty)
                              Text('Тип: ${account.accountType!}'),
                            if (account.status != null &&
                                account.status != 'Enabled')
                              Text(
                                'Статус: ${account.status!}',
                                style: TextStyle(
                                  color: Colors.orange.shade800,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                          ],
                        ),
                      ),
                      trailing: balance != null
                          ? Text(
                              (num.tryParse(balance.amount) ?? 0.0).toFormattedCurrency(balance.currency),
                              // '${balance.amount} ${balance.currency}',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                              ),
                            )
                          : const Text('Нет данных'),
                    );
                  }).toList(),
                ),
              );
            },
          );
        }

        // Возвращаем Scaffold, который использует подготовленные appBarTitle и body
        return Scaffold(
          appBar: AppBar(
            title:
                appBarTitle ??
                const Text(
                  'Мои счета',
                ), // Используем заголовок с суммой или простой
            actions: [
              if (_isRefreshing)
                const Padding(
                  padding: EdgeInsets.only(right: 16.0),
                  child: Center(
                    child: SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 3,
                      ),
                    ),
                  ),
                )
              else
                IconButton(
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Обновить данные',
                  onPressed: _triggerFullRefresh,
                ),
              IconButton(
                icon: const Icon(Icons.link),
                tooltip: 'Мои подключения',
                onPressed: _navigateToConnections,
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
          body: body,
        );
      },
    );
  }
}
