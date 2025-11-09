// lib/screens/account_details_screen.dart

import 'package:finapp/models/turnover_data.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/account.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../utils/formatting.dart';

class AccountDetailsScreen extends StatefulWidget {
  const AccountDetailsScreen({super.key});

  @override
  _AccountDetailsScreenState createState() => _AccountDetailsScreenState();
}

class _AccountDetailsScreenState extends State<AccountDetailsScreen> {
  late Account _account;
  TurnoverData? _turnoverData;
  bool _isLoading = false;
  bool _dataChanged = false;

  // VVV ГЛАВНОЕ ИСПРАВЛЕНИЕ: ДОБАВЛЯЕМ ФЛАГ ИНИЦИАЛИЗАЦИИ VVV
  bool _isInit = true;

  final ApiService _apiService = ApiService();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Запускаем инициализацию только один раз
    if (_isInit) {
      _account = ModalRoute.of(context)!.settings.arguments as Account;
      _fetchTurnover(); // Первоначальная загрузка оборотов
      setState(() {
        _isInit = false; // Устанавливаем флаг, чтобы больше не заходить сюда
      });
    }
    // ^^^ КОНЕЦ ИСПРАВЛЕНИЯ ^^^
  }

  Future<void> _selectDate(BuildContext context, bool isStatementDate) async {
    final initialDate =
        (isStatementDate ? _account.statementDate : _account.paymentDate) ??
        DateTime.now();

    final newDate = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );

    if (newDate == null || !mounted) return;

    setState(() {
      _isLoading = true;
      _turnoverData = null;
    });

    final authProvider = Provider.of<AuthProvider>(context, listen: false);

    try {
      final updatedAccount = await _apiService.updateAccountDates(
        userId: authProvider.userId!,
        accountId: _account.id,
        token: authProvider.token!,
        statementDate: isStatementDate ? newDate : _account.statementDate,
        paymentDate: isStatementDate ? _account.paymentDate : newDate,
      );

      setState(() {
        _account = updatedAccount;
        _dataChanged = true;
      });

      await _fetchTurnover();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ошибка обновления: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _fetchTurnover() async {
    if (_account.statementDate == null || _account.paymentDate == null) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    try {
      final turnover = await _apiService.getAccountTurnover(
        token: authProvider.token!,
        userId: authProvider.userId!,
        bankId: _account.bankId,
        apiAccountId: _account.apiAccountId,
        from: _account.statementDate!,
        to: _account.paymentDate!,
      );
      if (!mounted) return;
      setState(() {
        _turnoverData = turnover;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ошибка загрузки оборотов: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Если виджет еще не инициализирован, показываем заглушку
    if (_isInit) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return PopScope(
      canPop: false,
      onPopInvoked: (bool didPop) {
        if (didPop) return;
        Navigator.of(context).pop(_dataChanged);
      },
      child: Scaffold(
        appBar: AppBar(title: Text(_account.nickname)),
        body: ListView(
          padding: const EdgeInsets.all(16.0),
          children: [
            _buildInfoCard(),
            const SizedBox(height: 16),
            _buildDatesCard(),
            const SizedBox(height: 16),
            if (_isLoading)
              const Center(child: CircularProgressIndicator())
            else if (_turnoverData != null)
              GestureDetector(
                onTap: () {
                  Navigator.of(context).pushNamed(
                    '/transactions',
                    arguments: {
                      'account': _account,
                      'fromDate': _account.statementDate!,
                      'toDate': _account.paymentDate!,
                    },
                  );
                },
                child: _buildTurnoverCard(),
              ),
          ],
        ),
      ),
    );
  }

  // ... (все методы _build... остаются без изменений)
  Widget _buildInfoCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Основная информация',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Divider(),
            _buildInfoRow('Банк:', _account.bankName.toUpperCase()),
            if (_account.ownerName != null)
              _buildInfoRow('Владелец:', _account.ownerName!),
            _buildInfoRow('Тип:', _account.accountType ?? 'N/A'),
            _buildInfoRow('Статус:', _account.status ?? 'N/A'),
            _buildInfoRow('ID счета:', _account.apiAccountId),
            _buildInfoRow('ID клиента:', _account.bankClientId),
            const SizedBox(height: 16),
            Text('Балансы', style: Theme.of(context).textTheme.titleLarge),
            const Divider(),
            ..._account.balances.map(
              (b) => _buildInfoRow(
                '${b.type}:',
                (num.tryParse(b.amount) ?? 0).toFormattedCurrency(b.currency),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDatesCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Отчетный период',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Divider(),
            ListTile(
              title: const Text('Дата выписки'),
              subtitle: Text(
                _account.statementDate != null
                    ? DateFormat('dd.MM.yyyy').format(_account.statementDate!)
                    : 'Не указана',
              ),
              trailing: const Icon(Icons.calendar_today),
              onTap: () => _selectDate(context, true),
            ),
            ListTile(
              title: const Text('Дата платежа'),
              subtitle: Text(
                _account.paymentDate != null
                    ? DateFormat('dd.MM.yyyy').format(_account.paymentDate!)
                    : 'Не указана',
              ),
              trailing: const Icon(Icons.calendar_today),
              onTap: () => _selectDate(context, false),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTurnoverCard() {
    return Card(
      color: Colors.blue[50],
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Обороты за период',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Divider(),
            _buildInfoRow(
              'Приход:',
              _turnoverData!.totalCredit.toFormattedCurrency(
                _turnoverData!.currency,
              ),
              valueColor: Colors.green[700],
            ),
            _buildInfoRow(
              'Расход:',
              _turnoverData!.totalDebit.toFormattedCurrency(
                _turnoverData!.currency,
              ),
              valueColor: Colors.red[700],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value, {Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 16,
              color: valueColor,
            ),
          ),
        ],
      ),
    );
  }
}
