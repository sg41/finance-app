// lib/features/accounts/screens/accounts_dashboard_screen.dart

import 'package:flutter/material.dart';
import '../../../core/services/api_service.dart';
import '../../auth/screens/login_screen.dart';
import '../../home/screens/home_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AccountsDashboardScreen extends StatefulWidget {
  const AccountsDashboardScreen({super.key});

  @override
  _AccountsDashboardScreenState createState() =>
      _AccountsDashboardScreenState();
}

class _AccountsDashboardScreenState extends State<AccountsDashboardScreen> {
  final ApiService _apiService = ApiService();
  // Теперь это не Future, а сам список, чтобы мы могли его обновлять
  List<dynamic>? _connections;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadConnections();
  }

  // Метод для загрузки/обновления данных
  Future<void> _loadConnections() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final connections = await _apiService.getConnections();
      setState(() {
        _connections = connections;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Ошибка загрузки подключений: $e")),
        );
      }
    }
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear(); // Очищаем все данные
    if (mounted) {
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (context) => const LoginScreen()),
        (Route<dynamic> route) => false,
      );
    }
  }

  // Метод для перехода на экран добавления банка
  void _navigateAndRefresh() async {
    // Собираем имена уже подключенных банков для пометки
    final connectedBankNames =
        _connections?.map((c) => c['bank_name'] as String).toSet() ?? {};

    // Переходим на HomeScreen и ждем результат
    final result = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (context) =>
            HomeScreen(connectedBankNames: connectedBankNames),
      ),
    );

    // Если HomeScreen вернул `true`, значит, было добавлено новое подключение
    if (result == true && mounted) {
      // Обновляем список
      _loadConnections();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Мои подключения'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadConnections,
            tooltip: 'Обновить',
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _logout,
            tooltip: 'Выход',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _connections == null || _connections!.isEmpty
          ? const Center(
              child: Text(
                'У вас пока нет подключенных счетов.\nНажмите "+", чтобы добавить банк.',
                textAlign: TextAlign.center,
              ),
            )
          : RefreshIndicator(
              onRefresh: _loadConnections,
              child: ListView.builder(
                itemCount: _connections!.length,
                itemBuilder: (context, index) {
                  final connection = _connections![index];
                  return Card(
                    margin: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            connection['bank_name'].toString().toUpperCase(),
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text('ID клиента: ${connection['bank_client_id']}'),
                          Text('Статус: ${connection['status']}'),
                          // Дополнительная информация (если она есть в API ответе)
                          if (connection['consent_id'] != null)
                            Text('ID согласия: ${connection['consent_id']}'),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _navigateAndRefresh,
        child: const Icon(Icons.add),
        tooltip: 'Добавить банк',
      ),
    );
  }
}
