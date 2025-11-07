// lib/screens/connections_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../models/connection.dart';

class ConnectionsScreen extends StatefulWidget {
  const ConnectionsScreen({super.key});

  @override
  _ConnectionsScreenState createState() => _ConnectionsScreenState();
}

class _ConnectionsScreenState extends State<ConnectionsScreen> {
  late Future<List<Connection>> _connectionsFuture;
  final ApiService _apiService = ApiService();
  bool _dataChanged = false; // Флаг для отслеживания изменений

  @override
  void initState() {
    super.initState();
    _refreshConnections();
  }

  void _refreshConnections() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    setState(() {
      _connectionsFuture = _apiService.getConnections(
        authProvider.token!,
        authProvider.userId!,
      );
    });
  }

  Future<void> _deleteConnection(int connectionId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Подтверждение'),
        content: const Text('Вы уверены, что хотите удалить это подключение?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Отмена'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        final authProvider = Provider.of<AuthProvider>(context, listen: false);
        await _apiService.deleteConnection(
          authProvider.token!,
          authProvider.userId!,
          connectionId,
        );
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Подключение удалено.')));
        _dataChanged = true; // Устанавливаем флаг
        _refreshConnections();
      } catch (e) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Ошибка удаления: $e')));
      }
    }
  }

  void _navigateAndRefresh() async {
    final result = await Navigator.of(context).pushNamed('/add-connection');
    if (result == true && mounted) {
      _dataChanged = true; // Устанавливаем флаг
      _refreshConnections();
    }
  }

  @override
  Widget build(BuildContext context) {
    // --- vvv ВОЗВРАЩАЕМ РАБОЧУЮ ВЕРСИЮ PopScope vvv ---
    return PopScope(
      canPop: false,
      onPopInvoked: (bool didPop) {
        if (didPop) {
          return;
        }
        Navigator.of(context).pop(_dataChanged);
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Мои подключения')),
        body: FutureBuilder<List<Connection>>(
          future: _connectionsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            } else if (snapshot.hasError) {
              return Center(
                child: Text('Ошибка загрузки подключений: ${snapshot.error}'),
              );
            } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
              return const Center(child: Text('Подключений не найдено.'));
            }

            final connections = snapshot.data!;
            return ListView.builder(
              itemCount: connections.length,
              itemBuilder: (ctx, index) {
                final conn = connections[index];
                return Card(
                  margin: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  child: ListTile(
                    title: Text(
                      conn.bankName.toUpperCase(),
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ID клиента: ${conn.bankClientId}'),
                        Text('Статус: ${conn.status}'),
                        if (conn.consentId != null)
                          Text('ID согласия: ${conn.consentId}'),
                      ],
                    ),
                    trailing: IconButton(
                      icon: Icon(
                        Icons.remove_circle_outline,
                        color: Colors.red[700],
                      ),
                      onPressed: () => _deleteConnection(conn.id),
                      tooltip: 'Удалить подключение',
                    ),
                  ),
                );
              },
            );
          },
        ),
        floatingActionButton: FloatingActionButton(
          onPressed: _navigateAndRefresh,
          tooltip: 'Добавить подключение',
          child: const Icon(Icons.add),
        ),
      ),
    );
    // --- ^^^ КОНЕЦ ИСПРАВЛЕНИЯ ^^^ ---
  }
}
