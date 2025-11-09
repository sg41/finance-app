// lib/screens/login_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart'; // Для прямого вызова регистрации

enum AuthMode { Login, Signup }

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController(text: 'testuser@example.com');
  final _passwordController = TextEditingController(text: 'password');
  bool _isLoading = false;
  AuthMode _authMode = AuthMode.Login;
  final ApiService _apiService = ApiService();

  Future<void> _submit() async {
    setState(() {
      _isLoading = true;
    });

    try {
      if (_authMode == AuthMode.Login) {
        await Provider.of<AuthProvider>(
          context,
          listen: false,
        ).login(_emailController.text, _passwordController.text);
      } else {
        await _apiService.register(
          _emailController.text,
          _passwordController.text,
        );
        // После успешной регистрации, автоматически входим
        await Provider.of<AuthProvider>(
          context,
          listen: false,
        ).login(_emailController.text, _passwordController.text);
      }
    } catch (error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Произошла ошибка: ${error.toString()}')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _switchAuthMode() {
    setState(() {
      _authMode = _authMode == AuthMode.Login
          ? AuthMode.Signup
          : AuthMode.Login;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_authMode == AuthMode.Login ? 'Вход' : 'Регистрация'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: _emailController,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            TextField(
              controller: _passwordController,
              decoration: const InputDecoration(labelText: 'Пароль'),
              obscureText: true,
              onSubmitted: (_) => _submit(), // <-- ВХОД ПО ENTER
            ),
            const SizedBox(height: 20),
            if (_isLoading)
              const CircularProgressIndicator()
            else
              ElevatedButton(
                onPressed: _submit,
                child: Text(
                  _authMode == AuthMode.Login ? 'Войти' : 'Зарегистрироваться',
                ),
              ),
            TextButton(
              onPressed: _switchAuthMode,
              child: Text(
                _authMode == AuthMode.Login
                    ? 'У меня нет аккаунта'
                    : 'У меня уже есть аккаунт',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
