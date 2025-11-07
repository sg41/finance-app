// frontend/finapp/lib/screens/accounts_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../models/account.dart';
import '../models/connection.dart';

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
    // Запускаем первоначальную загрузку и фоновое обновление
    // после того, как первый кадр будет отрисован.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _triggerFullRefresh(isInitialLoad: true);
    });
  }

  /// Загружает данные из нашей БД для отображения в FutureBuilder.
  Future<List<BankWithAccounts>> _fetchAccountsFromDB() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    if (authProvider.isAuthenticated) {
      return _apiService.getAccounts(authProvider.token!, authProvider.userId!);
    }
    // Возвращаем пустой список, если пользователь не аутентифицирован.
    return Future.value([]);
  }

  /// Главный метод обновления: проверяет статусы ожидающих подключений,
  /// обновляет данные по активным и перезагружает UI.
  Future<void> _triggerFullRefresh({bool isInitialLoad = false}) async {
    // Предотвращаем запуск нового обновления, если одно уже идет.
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

      // Выполняем все задачи параллельно и ждем их завершения.
      await Future.wait(allTasks);

      // Не показываем SnackBar при первой невидимой загрузке после логина.
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
        // Перестраиваем FutureBuilder, чтобы он запросил свежие данные из БД.
        setState(() {
          _isRefreshing = false;
        });
      }
    }
  }

  /// Переходит на экран подключений и ждет результата.
  /// Если были изменения, запускает полное обновление.
  void _navigateToConnections() async {
    final result = await Navigator.of(context).pushNamed('/connections');
    if (result == true && mounted) {
      _triggerFullRefresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Мои счета'),
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
      body: FutureBuilder<List<BankWithAccounts>>(
        future: _fetchAccountsFromDB(),
        builder: (context, snapshot) {
          // Показываем индикатор только при самой первой загрузке.
          // Во время фоновых обновлений список остается на экране.
          if (snapshot.connectionState == ConnectionState.waiting &&
              !_isRefreshing) {
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
                              '${balance.amount} ${balance.currency}',
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
        },
      ),
    );
  }
}
