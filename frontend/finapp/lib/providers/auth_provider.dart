// lib/providers/auth_provider.dart

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

class AuthProvider with ChangeNotifier {
  String? _token;
  int? _userId;
  final ApiService _apiService = ApiService();

  String? get token => _token;
  int? get userId => _userId;
  bool get isAuthenticated => _token != null;

  Future<void> login(String email, String password) async {
    final response = await _apiService.login(email, password);
    _token = response['access_token'];
    _userId = response['user_id'];

    final prefs = await SharedPreferences.getInstance();
    prefs.setString('token', _token!);
    prefs.setInt('userId', _userId!);

    notifyListeners();
  }

  Future<bool> tryAutoLogin() async {
    final prefs = await SharedPreferences.getInstance();
    if (!prefs.containsKey('token')) {
      return false;
    }
    _token = prefs.getString('token');
    _userId = prefs.getInt('userId');

    return true;
  }

  void logout() async {
    _token = null;
    _userId = null;
    final prefs = await SharedPreferences.getInstance();
    prefs.clear();
    notifyListeners();
  }
}
