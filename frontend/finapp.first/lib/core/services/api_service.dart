// lib/core/services/api_service.dart

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart'; // <-- ДОБАВЬТЕ

class ApiService {
  final String _baseUrl =
      "http://127.0.0.1:8001"; // Измените на базовый URL вашего API

  Future<String?> _getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('auth_token');
  }

  // Эндпоинты аутентификации
  Future<Map<String, dynamic>> register(String email, String password) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/auth/login'),
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: {'username': email, 'password': password},
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', data['access_token']);
      await prefs.setString('user_id', data['user_id'].toString());
      return data;
    } else {
      throw Exception('Не удалось войти');
    }
  }

  // Эндпоинты банков
  Future<List<dynamic>> getBanks() async {
    String? token = await _getToken();
    final response = await http.get(
      Uri.parse('$_baseUrl/banks/'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body)['banks'];
    } else {
      throw Exception('Не удалось получить список банков');
    }
  }

  // Эндпоинты подключений
  Future<Map<String, dynamic>> createConnection(
    String bankName,
    String bankClientId,
  ) async {
    String? token = await _getToken();
    final prefs = await SharedPreferences.getInstance();
    String? userId = prefs.getString('user_id');
    final response = await http.post(
      Uri.parse('$_baseUrl/users/$userId/connections'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({'bank_name': bankName, 'bank_client_id': bankClientId}),
    );
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> checkConnectionStatus(int connectionId) async {
    String? token = await _getToken();
    final prefs = await SharedPreferences.getInstance();
    String? userId = prefs.getString('user_id');
    final response = await http.post(
      Uri.parse('$_baseUrl/users/$userId/connections/$connectionId'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Не удалось проверить статус подключения');
    }
  }

  Future<List<dynamic>> getConnections() async {
    String? token = await _getToken();
    final prefs = await SharedPreferences.getInstance();
    String? userId = prefs.getString('user_id');

    if (token == null || userId == null) {
      throw Exception('Пользователь не авторизован');
    }

    final response = await http.get(
      Uri.parse('$_baseUrl/users/$userId/connections'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['connections'];
    } else {
      throw Exception('Не удалось получить список подключений');
    }
  }
}
