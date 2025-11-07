// lib/screens/add_connection_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';

import '../models/bank.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';

class AddConnectionScreen extends StatefulWidget {
  const AddConnectionScreen({super.key});

  @override
  _AddConnectionScreenState createState() => _AddConnectionScreenState();
}

class _AddConnectionScreenState extends State<AddConnectionScreen> {
  late Future<List<Bank>> _banksFuture;
  final ApiService _apiService = ApiService();
  final _clientIdController = TextEditingController();

  @override
  void initState() {
    super.initState();
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    _banksFuture = _apiService.getAvailableBanks(authProvider.token!);
  }

  @override
  void dispose() {
    _clientIdController.dispose();
    super.dispose();
  }

  // vvv НОВЫЙ МЕТОД ДЛЯ ДИАЛОГА И ОТПРАВКИ ЗАПРОСА vvv
  Future<void> _showAddBankDialog(String bankName) async {
    _clientIdController.text = 'team076-'; // Предзаполняем для удобства

    final clientId = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Добавить $bankName'),
        content: TextField(
          controller: _clientIdController,
          decoration: const InputDecoration(labelText: 'ID клиента'),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Отмена'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop(_clientIdController.text);
            },
            child: const Text('Подключить'),
          ),
        ],
      ),
    );

    if (clientId != null && clientId.isNotEmpty && mounted) {
      final authProvider = Provider.of<AuthProvider>(context, listen: false);
      try {
        // --- vvv ИЗМЕНЕННАЯ ЛОГИКА ОБНОВЛЕНИЯ vvv ---

        // 1. Инициируем подключение и получаем ответ
        final response = await _apiService.initiateConnection(
          authProvider.token!,
          authProvider.userId!,
          bankName,
          clientId,
        );

        // Показываем сообщение от сервера (например, "инициировано" или "авто-одобрено")
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(response['message'] ?? 'Подключение обработано.'),
          ),
        );

        // 2. Если подключение было одобрено автоматически, сразу запускаем обновление счетов
        if (response['status'] == 'success_auto_approved' &&
            response['connection_id'] != null) {
          // Показываем индикатор, пока обновляются счета
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Обновляем данные по новому счету...'),
            ),
          );
          await _apiService.refreshConnection(
            authProvider.token!,
            authProvider.userId!,
            response['connection_id'],
          );
        }

        // 3. Возвращаемся на предыдущий экран, сигнализируя, что данные изменились
        Navigator.of(context).pop(true);

        // --- ^^^ КОНЕЦ ИЗМЕНЕНИЙ ^^^ ---
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceFirst('Exception: ', '')),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Добавить банк')),
      body: FutureBuilder<List<Bank>>(
        future: _banksFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text("Ошибка: ${snapshot.error}"));
          }
          if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text("Нет доступных банков."));
          }
          final banks = snapshot.data!;
          return ListView.builder(
            itemCount: banks.length,
            itemBuilder: (ctx, i) {
              final bank = banks[i];
              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: ListTile(
                  leading: SizedBox(
                    width: 40,
                    height: 40,
                    child:
                        bank.iconUrl != null && bank.iconUrl!.endsWith('.svg')
                        ? SvgPicture.network(
                            bank.iconUrl!,
                            placeholderBuilder: (context) =>
                                const Icon(Icons.business),
                          )
                        : bank.iconUrl != null
                        ? Image.network(
                            bank.iconUrl!,
                            errorBuilder: (ctx, err, stack) =>
                                const Icon(Icons.business),
                          )
                        : const Icon(Icons.business),
                  ),
                  title: Text(bank.name),
                  trailing: const Icon(Icons.add_circle_outline),
                  onTap: () => _showAddBankDialog(
                    bank.name,
                  ), // <-- ИСПОЛЬЗУЕМ НОВЫЙ МЕТОД
                ),
              );
            },
          );
        },
      ),
    );
  }
}
