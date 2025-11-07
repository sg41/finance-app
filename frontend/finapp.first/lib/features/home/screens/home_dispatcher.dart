// lib/features/home/screens/home_dispatcher.dart

import 'package:flutter/material.dart';
import '../../../core/services/api_service.dart';
import '../../accounts/screens/accounts_dashboard_screen.dart';
import 'home_screen.dart';

class HomeDispatcher extends StatelessWidget {
  const HomeDispatcher({super.key});

  @override
  Widget build(BuildContext context) {
    final apiService = ApiService();

    return FutureBuilder<List<dynamic>>(
      // Вызываем метод для получения подключений
      future: apiService.getConnections(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          // Пока идет проверка, показываем индикатор загрузки
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        if (snapshot.hasError) {
          // Если ошибка (например, токен истек), можно перенаправить на логин
          // Пока просто покажем ошибку
          return Scaffold(
            body: Center(child: Text("Ошибка: ${snapshot.error}")),
          );
        }

        // Проверяем, есть ли у пользователя подключения
        if (snapshot.hasData && snapshot.data!.isNotEmpty) {
          // Если есть, показываем приборную панель
          return const AccountsDashboardScreen();
        } else {
          // Если нет, показываем экран выбора банков (для нового пользователя)
          return const HomeScreen();
        }
      },
    );
  }
}
