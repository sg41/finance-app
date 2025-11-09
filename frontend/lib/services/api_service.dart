// frontend/finapp/lib/services/api_service.dart

import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';
import '../models/account.dart';
import '../models/connection.dart';
import '../models/bank.dart';
import '../models/turnover_data.dart';

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

  // vvv УПРОЩЕННАЯ И ИСПРАВЛЕННАЯ ФУНКЦИЯ vvv
  Future<List<BankWithAccounts>> getAccounts(String token, int userId) async {
    // 1. Делаем ОДИН запрос, чтобы получить плоский список всех счетов
    final accountsResponse = await http.get(
      Uri.parse('$API_BASE_URL/users/$userId/accounts/'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (accountsResponse.statusCode != 200) {
      throw Exception('Failed to load accounts from database');
    }

    final accountsBody = json.decode(utf8.decode(accountsResponse.bodyBytes));
    final List<dynamic> accountsJson = accountsBody['accounts'];

    // 2. Группируем счета по имени банка на стороне клиента
    final Map<String, List<Account>> accountsByBank = {};

    for (var accJson in accountsJson) {
      final account = Account.fromJson(accJson);
      // Используем bankName, который теперь приходит вместе со счетом
      final String bankName = account.bankName;

      accountsByBank.putIfAbsent(bankName, () => []);
      accountsByBank[bankName]!.add(account);
    }

    // 3. Преобразуем карту в список объектов BankWithAccounts для UI
    final bankList = accountsByBank.entries.map((entry) {
      return BankWithAccounts(name: entry.key, accounts: entry.value);
    }).toList();

    // vvv ДОБАВЛЯЕМ СОРТИРОВКУ ПО ИМЕНИ vvv
    bankList.sort((a, b) => a.name.compareTo(b.name));
    // ^^^ КОНЕЦ ИЗМЕНЕНИЙ ^^^

    return bankList;
  }

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

  // vvv НОВЫЙ МЕТОД vvv
  Future<List<Bank>> getAvailableBanks(String token) async {
    final response = await http.get(
      Uri.parse('$API_BASE_URL/banks/'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode == 200) {
      final body = json.decode(utf8.decode(response.bodyBytes));
      final List banksJson = body['banks'];
      return banksJson.map((json) => Bank.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load available banks');
    }
  }

  // vvv ИЗМЕНЯЕМ ЭТОТ МЕТОД, ЧТОБЫ ОН ВОЗВРАЩАЛ ОТВЕТ СЕРВЕРА vvv
  Future<Map<String, dynamic>> initiateConnection(
    String token,
    int userId,
    String bankName,
    String bankClientId,
  ) async {
    final response = await http.post(
      Uri.parse('$API_BASE_URL/users/$userId/connections/'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: json.encode({
        'bank_name': bankName,
        'bank_client_id': bankClientId,
      }),
    );

    if (response.statusCode == 200) {
      // Возвращаем тело ответа, чтобы получить status и connection_id
      return json.decode(utf8.decode(response.bodyBytes));
    } else {
      String errorMessage =
          'Ошибка при добавлении банка. Код: ${response.statusCode}';
      try {
        final errorBody = json.decode(utf8.decode(response.bodyBytes));
        if (errorBody['detail'] != null) {
          errorMessage = 'Ошибка: ${errorBody['detail']}';
        }
      } catch (e) {
        errorMessage += '\nОтвет сервера: ${utf8.decode(response.bodyBytes)}';
      }
      throw Exception(errorMessage);
    }
  }

  // vvv НОВЫЙ МЕТОД vvv
  Future<void> refreshConnection(
    String token,
    int userId,
    int connectionId,
  ) async {
    final response = await http.post(
      Uri.parse('$API_BASE_URL/users/$userId/accounts/$connectionId/refresh'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) {
      // Этот метод может вызываться в фоне, поэтому просто логируем ошибку,
      // не бросая исключение, которое может прервать другие обновления.
      print('Failed to refresh connection $connectionId: ${response.body}');
    }
  }

  // vvv НОВЫЙ МЕТОД vvv
  Future<void> deleteConnection(
    String token,
    int userId,
    int connectionId,
  ) async {
    final response = await http.delete(
      Uri.parse('$API_BASE_URL/users/$userId/connections/$connectionId'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to delete connection');
    }
  }

  // vvv НОВЫЙ МЕТОД vvv
  Future<void> register(String email, String password) async {
    final response = await http.post(
      Uri.parse('$API_BASE_URL/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'email': email, 'password': password}),
    );
    // 200 - создан, 400 - уже существует. Для UI оба ок.
    if (response.statusCode != 200 && response.statusCode != 400) {
      throw Exception('Failed to register');
    }
  }

  // vvv НОВЫЙ МЕТОД ДЛЯ ПРОВЕРКИ СТАТУСА vvv
  Future<void> checkConsentStatus(
    String token,
    int userId,
    int connectionId,
  ) async {
    final response = await http.post(
      Uri.parse('$API_BASE_URL/users/$userId/connections/$connectionId'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode != 200) {
      // Логируем, но не бросаем исключение, чтобы не прерывать другие фоновые задачи
      print(
        'Failed to check consent status for connection $connectionId: ${response.body}',
      );
    } else {
      final body = json.decode(utf8.decode(response.bodyBytes));
      print('Checked status for connection $connectionId: ${body['status']}');
    }
  }

  Future<Account> updateAccountDates({
    required int userId,
    required int accountId,
    required String token,
    DateTime? statementDate,
    DateTime? paymentDate,
  }) async {
    final Map<String, dynamic> body = {};
    if (statementDate != null) {
      // Форматируем дату в "YYYY-MM-DD"
      body['statement_date'] = statementDate.toIso8601String().substring(0, 10);
    }
    if (paymentDate != null) {
      body['payment_date'] = paymentDate.toIso8601String().substring(0, 10);
    }

    final response = await http.put(
      Uri.parse('$API_BASE_URL/users/$userId/accounts/$accountId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: json.encode(body),
    );

    if (response.statusCode == 200) {
      return Account.fromJson(json.decode(utf8.decode(response.bodyBytes)));
    } else {
      throw Exception('Failed to update account details');
    }
  }

  // VVV ДОБАВЬТЕ ЭТОТ МЕТОД VVV
  Future<TurnoverData> getAccountTurnover({
    required String token,
    required int userId,
    required int bankId, // Этот ID нужен для эндпоинта
    required String apiAccountId,
    required DateTime from,
    required DateTime to,
  }) async {
    final uri =
        Uri.parse(
          '$API_BASE_URL/users/$userId/banks/$bankId/accounts/$apiAccountId/turnover',
        ).replace(
          queryParameters: {
            'from_booking_date_time': from.toUtc().toIso8601String(),
            'to_booking_date_time': to.toUtc().toIso8601String(),
          },
        );

    final response = await http.get(
      uri,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      // Используем utf8.decode для правильной обработки кириллицы
      return TurnoverData.fromJson(
        json.decode(utf8.decode(response.bodyBytes)),
      );
    } else {
      throw Exception('Failed to load turnover data: ${response.body}');
    }
  }
}
