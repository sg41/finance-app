// lib/main.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'screens/accounts_screen.dart';
import 'screens/login_screen.dart';
import 'screens/connections_screen.dart';
import 'screens/add_connection_screen.dart'; // <-- ДОБАВИТЬ

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (ctx) => AuthProvider(),
      child: Consumer<AuthProvider>(
        builder: (ctx, auth, _) => MaterialApp(
          title: 'FinApp',
          theme: ThemeData(
            primarySwatch: Colors.deepPurple,
            visualDensity: VisualDensity.adaptivePlatformDensity,
          ),
          home: auth.isAuthenticated
              ? const AccountsScreen()
              : FutureBuilder(
                  future: auth.tryAutoLogin(),
                  builder: (ctx, authResultSnapshot) =>
                      authResultSnapshot.connectionState ==
                          ConnectionState.waiting
                      ? const Scaffold(
                          body: Center(child: CircularProgressIndicator()),
                        )
                      : const LoginScreen(),
                ),
          routes: {
            '/connections': (ctx) => const ConnectionsScreen(),
            '/add-connection': (ctx) =>
                const AddConnectionScreen(), // <-- ДОБАВИТЬ
          },
        ),
      ),
    );
  }
}
