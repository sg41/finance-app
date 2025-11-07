// frontend/finapp/lib/services/api_service.dart

import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';
import '../models/account.dart';
import '../models/connection.dart';

class ApiService {
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await http.post(
      Uri.parse('$API_BASE_URL/auth/login'),
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: {'username': email, 'password': password},
    );

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to login');
    }
  }

  // --- vvv ИЗМЕНЕННАЯ ФУНКЦИЯ vvv ---
  Future<List<BankWithAccounts>> getAccounts(String token, int userId) async {
    // 1. Получаем все сохраненные счета пользователя из нашей БД
    final accountsResponse = await http.get(
      Uri.parse('$API_BASE_URL/users/$userId/accounts/'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (accountsResponse.statusCode != 200) {
      throw Exception('Failed to load accounts from database');
    }

    // 2. Получаем все подключения, чтобы сопоставить connection_id с именем банка
    final connections = await getConnections(token, userId);

    // Создаем карту для быстрого поиска имени банка по ID подключения
    final Map<int, String> connectionIdToBankName = {
      for (var conn in connections) conn.id: conn.bankName,
    };

    final accountsBody = json.decode(utf8.decode(accountsResponse.bodyBytes));
    final List<dynamic> accountsJson = accountsBody['accounts'];

    // Группируем счета по имени банка
    final Map<String, List<Account>> accountsByBank = {};

    for (var accJson in accountsJson) {
      final int connectionId = accJson['connection_id'];
      final String? bankName = connectionIdToBankName[connectionId];

      if (bankName != null) {
        final account = Account.fromJson(accJson);
        // Если для банка еще нет списка счетов, создаем его
        accountsByBank.putIfAbsent(bankName, () => []);
        // Добавляем счет в список
        accountsByBank[bankName]!.add(account);
      }
    }

    // 3. Преобразуем сгруппированную карту в список объектов BankWithAccounts для UI
    return accountsByBank.entries.map((entry) {
      return BankWithAccounts(name: entry.key, accounts: entry.value);
    }).toList();
  }
  // --- ^^^ КОНЕЦ ИЗМЕНЕННОЙ ФУНКЦИИ ^^^ ---

  Future<List<Connection>> getConnections(String token, int userId) async {
    final response = await http.get(
      Uri.parse('$API_BASE_URL/users/$userId/connections/'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      final body = json.decode(utf8.decode(response.bodyBytes));
      final List connectionsJson = body['connections'];
      return connectionsJson.map((json) => Connection.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load connections');
    }
  }
}
