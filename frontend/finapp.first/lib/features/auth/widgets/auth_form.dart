// lib/features/auth/widgets/auth_form.dart

import 'package:flutter/material.dart';
import '../../../core/services/api_service.dart';
import '../../home/screens/home_dispatcher.dart'; // <-- ИМПОРТИРУЕМ НОВЫЙ ДИСПЕТЧЕР
import '../screens/register_screen.dart'; // <-- 1. ДОБАВЛЕН НУЖНЫЙ ИМПОРТ

class AuthForm extends StatefulWidget {
  final bool isLogin;
  const AuthForm({super.key, required this.isLogin});

  @override
  _AuthFormState createState() => _AuthFormState();
}

class _AuthFormState extends State<AuthForm> {
  final _formKey = GlobalKey<FormState>();
  String _email = '';
  String _password = '';
  final ApiService _apiService = ApiService();
  bool _isLoading = false;
  late FocusNode _passwordFocusNode;

  @override
  void initState() {
    super.initState();
    _passwordFocusNode = FocusNode();
  }

  @override
  void dispose() {
    _passwordFocusNode.dispose();
    super.dispose();
  }

  void _submit() async {
    if (_formKey.currentState!.validate()) {
      _formKey.currentState!.save();
      setState(() {
        _isLoading = true;
      });
      try {
        if (widget.isLogin) {
          await _apiService.login(_email, _password);
        } else {
          await _apiService.register(_email, _password);
          // Автоматически входим после регистрации
          await _apiService.login(_email, _password);
        }
        // Проверяем, смонтирован ли виджет, перед навигацией
        if (mounted) {
          Navigator.of(context).pushReplacement(
            // --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            // Теперь мы всегда переходим на диспетчер,
            // который сам решит, что показать.
            MaterialPageRoute(builder: (context) => const HomeDispatcher()),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text('Ошибка: ${e.toString()}')));
        }
      } finally {
        if (mounted) {
          setState(() {
            _isLoading = false;
          });
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextFormField(
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              validator: (value) => value!.isEmpty || !value.contains('@')
                  ? 'Введите корректный email'
                  : null,
              onSaved: (value) => _email = value!,
              onFieldSubmitted: (_) =>
                  FocusScope.of(context).requestFocus(_passwordFocusNode),
            ),

            TextFormField(
              decoration: const InputDecoration(labelText: 'Пароль'),
              obscureText: true,
              focusNode: _passwordFocusNode,
              textInputAction: TextInputAction.done,
              validator: (value) => value!.length < 6
                  ? 'Пароль должен быть не менее 6 символов'
                  : null,
              onSaved: (value) => _password = value!,
              onFieldSubmitted: (_) => _submit(), // Нажатие Enter вызывает вход
            ),
            const SizedBox(height: 20),
            if (_isLoading)
              const CircularProgressIndicator()
            else
              ElevatedButton(
                onPressed: _submit,
                child: Text(widget.isLogin ? 'Войти' : 'Зарегистрироваться'),
              ),
            const SizedBox(height: 10),
            // --- 2. УЛУЧШЕННАЯ ЛОГИКА КНОПОК НАВИГАЦИИ ---
            if (!_isLoading)
              if (widget.isLogin)
                TextButton(
                  onPressed: () {
                    // Переход на экран регистрации
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (ctx) => const RegisterScreen(),
                      ),
                    );
                  },
                  child: const Text("Нет аккаунта? Зарегистрируйтесь"),
                )
              else
                TextButton(
                  onPressed: () {
                    // Возврат на экран входа
                    Navigator.of(context).pop();
                  },
                  child: const Text("Уже есть аккаунт? Войти"),
                ),
          ],
        ),
      ),
    );
  }
}
