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

  @override
  void initState() {
    super.initState();
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    _connectionsFuture = _apiService.getConnections(
      authProvider.token!,
      authProvider.userId!,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        conn.bankName.toUpperCase(),
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text('ID клиента: ${conn.bankClientId}'),
                      Text('Статус: ${conn.status}'),
                      if (conn.consentId != null)
                        Text('ID согласия: ${conn.consentId}'),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
