// lib/features/auth/screens/login_screen.dart

import 'package:flutter/material.dart';
import '../widgets/auth_form.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Вход")),
      body: const AuthForm(isLogin: true),
    );
  }
}