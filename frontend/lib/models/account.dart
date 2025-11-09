// lib/models/account.dart

class Account {
  final int id;
  final String apiAccountId;
  final String nickname;
  final String currency;
  final List<Balance> balances;
  // vvv НОВЫЕ ПОЛЯ vvv
  final String? ownerName;
  final String? accountType;
  final String? status;
  final String bankClientId;
  final String bankName;
  final DateTime? statementDate;
  final DateTime? paymentDate;

  Account({
    required this.id,
    required this.apiAccountId,
    required this.nickname,
    required this.currency,
    required this.balances,
    // vvv ОБНОВЛЯЕМ КОНСТРУКТОР vvv
    this.ownerName,
    this.accountType,
    this.status,
    required this.bankClientId,
    required this.bankName,
    this.statementDate,
    this.paymentDate,
  });

  factory Account.fromJson(Map<String, dynamic> json) {
    var balanceList = json['balance_data'] as List? ?? [];
    List<Balance> balances = balanceList
        .map((i) => Balance.fromJson(i))
        .toList();

    // vvv ЛОГИКА ИЗВЛЕЧЕНИЯ НОВЫХ ДАННЫХ vvv
    String? ownerName;
    final ownerData = json['owner_data'] as List?;
    if (ownerData != null && ownerData.isNotEmpty) {
      // Данные о владельце - это массив, берем имя из первого элемента
      final firstOwner = ownerData.first as Map<String, dynamic>?;
      if (firstOwner != null && firstOwner.containsKey('name')) {
        ownerName = firstOwner['name'];
      }
    }
    // ^^^ КОНЕЦ ЛОГИКИ ^^^

    return Account(
      id: json['id'],
      apiAccountId: json['api_account_id'],
      nickname: json['nickname'] ?? 'N/A',
      currency: json['currency'] ?? 'N/A',
      balances: balances,
      // vvv ПРИСВАИВАЕМ НОВЫЕ ПОЛЯ vvv
      ownerName: ownerName,
      accountType: json['account_type'],
      status: json['status'],
      bankClientId: json['bank_client_id'] ?? 'N/A',
      bankName: json['bank_name'] ?? 'N/A',
      statementDate: json['statement_date'] != null
          ? DateTime.parse(json['statement_date'])
          : null,
      paymentDate: json['payment_date'] != null
          ? DateTime.parse(json['payment_date'])
          : null,
    );
  }
}

class Balance {
  final String type;
  final String amount;
  final String currency;

  Balance({required this.type, required this.amount, required this.currency});

  factory Balance.fromJson(Map<String, dynamic> json) {
    return Balance(
      type: json['type'] ?? 'N/A',
      amount: json['amount']?['amount'] ?? '0.00',
      currency: json['amount']?['currency'] ?? '',
    );
  }
}

class BankWithAccounts {
  final String name;
  final List<Account> accounts;

  BankWithAccounts({required this.name, required this.accounts});

  // vvv НОВЫЙ ГЕТТЕР ДЛЯ ПОДСЧЕТА СУММЫ vvv
  double get totalBalance {
    // Используем fold для итерации по счетам и суммирования
    return accounts.fold(0.0, (sum, account) {
      try {
        // Ищем баланс типа 'InterimAvailable'
        final availableBalance = account.balances.firstWhere(
          (b) => b.type == 'InterimAvailable',
          // Если такого нет, возвращаем "пустой" баланс, чтобы не было ошибки
          orElse: () => Balance(type: '', amount: '0.0', currency: ''),
        );

        // Пытаемся распарсить сумму и добавить к общей
        final amount = double.tryParse(availableBalance.amount) ?? 0.0;
        return sum + amount;
      } catch (e) {
        // В случае любой ошибки просто добавляем 0 и продолжаем
        return sum;
      }
    });
  }
  // ^^^ КОНЕЦ НОВОГО ГЕТТЕРА ^^^

  factory BankWithAccounts.fromJson(Map<String, dynamic> json) {
    var accountList = json['account'] as List? ?? [];
    List<Account> accounts = accountList
        .map((i) => Account.fromJson(i))
        .toList();
    return BankWithAccounts(name: json['name'], accounts: accounts);
  }
}
