// lib/features/auth/screens/register_screen.dart

import 'package:flutter/material.dart';
import '../widgets/auth_form.dart';

class RegisterScreen extends StatelessWidget {
  const RegisterScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Регистрация")),
      body: const AuthForm(isLogin: false),
    );
  }
}