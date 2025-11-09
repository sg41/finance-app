// lib/main.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/accounts_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/banks_provider.dart';
import 'providers/connections_provider.dart';
import 'screens/accounts_screen.dart';
import 'screens/login_screen.dart';
import 'screens/connections_screen.dart';
import 'screens/add_connection_screen.dart';
import 'screens/account_details_screen.dart'; // <-- ДОБАВИТЬ
import 'screens/transactions_screen.dart'; // <-- ДОБАВЬТЕ ЭТОТ ИМПОРТ

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (ctx) => AuthProvider()),
        ChangeNotifierProxyProvider<AuthProvider, BanksProvider>(
          create: (ctx) => BanksProvider(null),
          update: (ctx, auth, previousBanksProvider) => BanksProvider(auth),
        ),
        ChangeNotifierProxyProvider<AuthProvider, ConnectionsProvider>(
          create: (ctx) => ConnectionsProvider(null),
          update: (ctx, auth, previousConnectionsProvider) =>
              ConnectionsProvider(auth),
        ),
        // VVV ИЗМЕНЕНИЕ ЗДЕСЬ: Убираем зависимость от ConnectionsProvider VVV
        ChangeNotifierProxyProvider<AuthProvider, AccountsProvider>(
          create: (ctx) => AccountsProvider(null),
          update: (ctx, auth, previousAccountsProvider) =>
              AccountsProvider(auth),
        ),
        // --- КОНЕЦ ИЗМЕНЕНИЯ ---
      ],
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
            '/add-connection': (ctx) => const AddConnectionScreen(),
            '/account-details': (ctx) => const AccountDetailsScreen(),
            '/transactions': (ctx) =>
                const TransactionsScreen(), // <-- ДОБАВЬТЕ ЭТУ СТРОКУ
          },
        ),
      ),
    );
  }
}
