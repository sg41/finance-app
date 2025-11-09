// lib/screens/transactions_screen.dart

import 'dart:typed_data';
import 'package:excel/excel.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/account.dart';
import '../models/transaction.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../utils/formatting.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key});

  @override
  _TransactionsScreenState createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  late Future<List<Transaction>> _transactionsFuture;
  final ApiService _apiService = ApiService();

  // VVV ДОБАВЛЯЕМ НОВЫЕ ПОЛЯ СОСТОЯНИЯ VVV
  List<Transaction> _transactions = [];
  bool _isExporting = false;
  // ^^^ КОНЕЦ НОВЫХ ПОЛЕЙ ^^^

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args =
        ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>;
    final account = args['account'] as Account;
    final fromDate = args['fromDate'] as DateTime;
    final toDate = args['toDate'] as DateTime;
    final authProvider = Provider.of<AuthProvider>(context, listen: false);

    _transactionsFuture = _apiService.getTransactions(
      token: authProvider.token!,
      userId: authProvider.userId!,
      bankId: account.bankId,
      apiAccountId: account.apiAccountId,
      from: fromDate,
      to: toDate,
    );
  }

  // VVV ДОБАВЛЯЕМ НОВЫЙ МЕТОД ДЛЯ ЭКСПОРТА VVV
  Future<void> _exportToExcel() async {
    if (_transactions.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Нет данных для экспорта.')));
      return;
    }

    setState(() {
      _isExporting = true;
    });

    try {
      var excel = Excel.createExcel();
      Sheet sheetObject = excel['Транзакции'];

      List<String> headers = [
        "Дата и время",
        "Описание",
        "Сумма",
        "Валюта",
        "Тип (Приход/Расход)",
        "Статус",
      ];
      sheetObject.appendRow(headers.map((e) => TextCellValue(e)).toList());

      for (var tx in _transactions) {
        final isCredit = tx.creditDebitIndicator.toLowerCase() == 'credit';
        List<CellValue> row = [
          TextCellValue(
            DateFormat('dd.MM.yyyy HH:mm').format(tx.bookingDateTime.toLocal()),
          ),
          TextCellValue(tx.transactionInformation ?? ''),
          DoubleCellValue(double.tryParse(tx.amount) ?? 0.0),
          TextCellValue(tx.currency),
          TextCellValue(isCredit ? 'Приход' : 'Расход'),
          TextCellValue(tx.status),
        ];
        sheetObject.appendRow(row);
      }

      // ИСПРАВЛЕНИЕ: Полностью убираем цикл авто-подбора ширины,
      // так как этого метода нет в используемой версии пакета.
      /*
      for (var i = 0; i < headers.length; i++) {
        sheetObject.autoFitColumn(i); 
      }
      */

      final fileBytes = excel.encode();
      if (fileBytes != null) {
        final date = DateFormat('yyyy-MM-dd').format(DateTime.now());

        await FileSaver.instance.saveFile(
          name: 'transactions_$date.xlsx',
          bytes: Uint8List.fromList(fileBytes),
          mimeType: MimeType.microsoftExcel,
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ошибка экспорта: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isExporting = false;
        });
      }
    }
  }
  // ^^^ КОНЕЦ НОВОГО МЕТОДА ^^^

  @override
  Widget build(BuildContext context) {
    final args =
        ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>;
    final fromDate = args['fromDate'] as DateTime;
    final toDate = args['toDate'] as DateTime;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Транзакции'),
            Text(
              '${DateFormat('dd.MM.yy').format(fromDate)} - ${DateFormat('dd.MM.yy').format(toDate)}',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.normal,
              ),
            ),
          ],
        ),
        // VVV ДОБАВЛЯЕМ КНОПКУ ЭКСПОРТА VVV
        actions: [
          if (_isExporting)
            const Padding(
              padding: EdgeInsets.only(right: 16.0),
              child: Center(
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(color: Colors.white),
                ),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.download),
              tooltip: 'Экспорт в Excel',
              onPressed: _transactions.isEmpty ? null : _exportToExcel,
            ),
        ],
        // ^^^ КОНЕЦ ИЗМЕНЕНИЙ ^^^
      ),
      body: FutureBuilder<List<Transaction>>(
        future: _transactionsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text("Ошибка загрузки: ${snapshot.error}"));
          }
          if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(
              child: Text("Транзакций за период не найдено."),
            );
          }

          // Сохраняем данные в состояние для доступа из функции экспорта
          _transactions = snapshot.data!;
          _transactions.sort(
            (a, b) => b.bookingDateTime.compareTo(a.bookingDateTime),
          );

          return ListView.builder(
            itemCount: _transactions.length,
            itemBuilder: (ctx, i) {
              final tx = _transactions[i];
              final isCredit =
                  tx.creditDebitIndicator.toLowerCase() == 'credit';
              final amount = num.tryParse(tx.amount) ?? 0.0;

              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: ListTile(
                  leading: Icon(
                    isCredit ? Icons.arrow_downward : Icons.arrow_upward,
                    color: isCredit ? Colors.green : Colors.red,
                  ),
                  title: Text(
                    tx.transactionInformation ?? 'Без описания',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    DateFormat(
                      'dd.MM.yyyy HH:mm',
                    ).format(tx.bookingDateTime.toLocal()),
                  ),
                  trailing: Text(
                    amount.toFormattedCurrency(tx.currency),
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: isCredit ? Colors.green[700] : Colors.red[700],
                    ),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
