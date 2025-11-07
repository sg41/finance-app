// lib/features/home/screens/home_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../../accounts/screens/accounts_dashboard_screen.dart';
import '../../../core/services/api_service.dart';
// import '../../accounts/screens/accounts_screen.dart';

class HomeScreen extends StatefulWidget {
  final Set<String>? connectedBankNames;

  const HomeScreen({super.key, this.connectedBankNames});

  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  late Future<List<dynamic>> _banks;
  // Контроллер для текстового поля в диалоге
  final TextEditingController _bankClientIdController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _banks = _apiService.getBanks();
  }

  @override
  void dispose() {
    _bankClientIdController.dispose();
    super.dispose();
  }

  // --- НОВЫЙ МЕТОД: ДИАЛОГ ДЛЯ ВВОДА ID КЛИЕНТА ---
  Future<void> _showClientIdDialog(String bankName) async {
    _bankClientIdController.clear(); // Очищаем поле перед показом

    return showDialog<void>(
      context: context,
      barrierDismissible: true, // Разрешаем закрытие по тапу вне диалога
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Подключить $bankName'),
          content: SingleChildScrollView(
            child: ListBody(
              children: <Widget>[
                const Text(
                  'Пожалуйста, введите ваш идентификатор клиента банка.',
                ),
                TextField(
                  controller: _bankClientIdController,
                  decoration: const InputDecoration(
                    hintText: 'Например, my-client-id-123',
                  ),
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              child: const Text('Отмена'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
            TextButton(
              child: const Text('Подключить'),
              onPressed: () {
                // Получаем введенный ID и вызываем подключение
                final clientId = _bankClientIdController.text;
                if (clientId.isNotEmpty) {
                  Navigator.of(context).pop(); // Закрываем диалог
                  _connectToBank(bankName, clientId); // Вызываем подключение
                }
              },
            ),
          ],
        );
      },
    );
  }

  // ВАЖНО: Эта функция корректирует URL для работы с эмулятором Android
  String _fixLocalhostUrl(String url) {
    // В вебе localhost работает как есть.
    // Проверяем, что мы НЕ в вебе И что платформа - Android.
    if (!kIsWeb && Theme.of(context).platform == TargetPlatform.android) {
      return url.replaceAll('localhost', '10.0.2.2');
    }
    return url;
  }

  Widget _buildBankIcon(String iconUrl) {
    final fixedUrl = _fixLocalhostUrl(iconUrl);

    // Проверяем, является ли иконка SVG
    if (fixedUrl.toLowerCase().endsWith('.svg')) {
      return SvgPicture.network(
        fixedUrl,
        placeholderBuilder: (context) => const CircularProgressIndicator(),
        width: 40,
        height: 40,
      );
    } else {
      // Для других форматов (PNG, JPG) используем Image.network
      return Image.network(
        fixedUrl,
        width: 40,
        height: 40,
        // Виджет, который будет показан во время загрузки
        loadingBuilder: (context, child, loadingProgress) {
          if (loadingProgress == null) return child;
          return const Center(child: CircularProgressIndicator());
        },
        // Виджет, который будет показан в случае ошибки загрузки
        errorBuilder: (context, error, stackTrace) {
          return const Icon(Icons.error, size: 40);
        },
      );
    }
  }

  void _connectToBank(String bankName, String bankClientId) async {
    // Показываем индикатор загрузки
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(child: CircularProgressIndicator()),
    );

    try {
      final connection = await _apiService.createConnection(
        bankName,
        bankClientId,
      );

      if (connection['status'] == 'success_auto_approved' ||
          connection['status'] == 'awaiting_authorization' ||
          connection['status'] == 'already_initiated') {
        // Сначала всегда закрываем диалог загрузки
        Navigator.of(context).pop();

        // Определяем, в каком режиме мы находимся
        final isAddingMode = widget.connectedBankNames != null;

        // --- ИЗМЕНЕНИЕ ЗДЕСЬ: ЛОГИКА НАВИГАЦИИ ---
        if (isAddingMode) {
          // Сценарий 1: Существующий пользователь.
          // Мы пришли с дашборда, поэтому просто возвращаемся на него,
          // отправляя сигнал `true` для обновления.
          Navigator.of(context).pop(true);
        } else {
          // Сценарий 2: Новый пользователь.
          // Он добавил свой первый банк. Заменяем текущий экран (HomeScreen)
          // на главный дашборд. `pushReplacement` не позволяет вернуться назад.
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (context) => const AccountsDashboardScreen(),
            ),
          );
        }
      } else {
        throw Exception(connection['message'] ?? 'Неизвестная ошибка');
      }
    } catch (e) {
      // Закрываем индикатор загрузки, если он еще открыт
      if (Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
      }
      // Показываем ошибку
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка подключения: ${e.toString()}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // Определяем, является ли этот экран "главным" или открыт для добавления
    final isAddingMode = widget.connectedBankNames != null;

    return Scaffold(
      appBar: AppBar(
        title: Text(isAddingMode ? 'Добавить банк' : 'Выберите банк'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Показываем приветствие только для новых пользователей
            if (!isAddingMode)
              const Padding(
                padding: EdgeInsets.all(8.0),
                child: Text(
                  "Добро пожаловать! Подключите свой первый банковский счет, чтобы начать.",
                  style: TextStyle(fontSize: 18),
                ),
              ),
            const SizedBox(height: 10),
            Expanded(
              child: FutureBuilder<List<dynamic>>(
                future: _banks,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  // ... (обработка ошибок) ...

                  return ListView.builder(
                    itemCount: snapshot.data!.length,
                    itemBuilder: (context, index) {
                      final bank = snapshot.data![index];
                      final bankName = bank['name'] as String;
                      // Проверяем, подключен ли уже этот банк
                      final isConnected =
                          widget.connectedBankNames?.contains(bankName) ??
                          false;

                      return Card(
                        margin: const EdgeInsets.symmetric(
                          vertical: 4,
                          horizontal: 8,
                        ),
                        color: isConnected
                            ? Colors.grey[300]
                            : null, // Серый фон для подключенных
                        child: ListTile(
                          leading: _buildBankIcon(bank['icon_url']),
                          title: Text(bankName),
                          // Помечаем, если хотя бы один аккаунт этого банка уже подключен
                          trailing: isConnected
                              ? const Icon(
                                  Icons.check_circle_outline,
                                  color: Colors.blue,
                                )
                              : null,
                          // ВСЕГДА вызываем диалог по нажатию
                          onTap: () => _showClientIdDialog(bankName),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
