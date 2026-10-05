import argparse
import json
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal('0.01')
STATUSES = {'open', 'redeemed', 'sold'}


def number(value, label, minimum, maximum):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'{label}: требуется число') from exc
    if not result.is_finite() or not minimum <= result <= maximum:
        raise ValueError(f'{label}: недопустимое значение')
    return result


def validate(loan):
    """Проверка одной записи. Дата grace_until задается явно по договору."""
    if not isinstance(loan, dict):
        raise ValueError('Запись должна быть объектом')
    required = {'id', 'principal', 'daily_rate', 'issued', 'due',
                'grace_until', 'status', 'cap_ratio'}
    if not required <= loan.keys():
        raise ValueError('Не заполнены обязательные поля')
    if not isinstance(loan['id'], str) or not loan['id'].strip():
        raise ValueError('Пустой номер договора')
    principal = number(loan['principal'], 'Сумма', CENT, Decimal('100000000'))
    if principal != principal.quantize(CENT):
        raise ValueError('Сумма должна быть задана с точностью до копейки')
    rate = number(loan['daily_rate'], 'Ставка', Decimal('0'), Decimal('0.01'))
    cap = number(loan['cap_ratio'], 'Предел процентов', Decimal('0'), Decimal('1'))
    issued, due, grace = [date.fromisoformat(loan[k])
                          for k in ('issued', 'due', 'grace_until')]
    if not issued < due < grace:
        raise ValueError('Нарушен порядок дат')
    if loan['status'] not in STATUSES:
        raise ValueError('Неизвестный статус')
    return principal, rate, cap, issued, due, grace


def quote(loan, on_date):
    """Простой процент без промежуточного округления и частичных платежей."""
    principal, rate, cap, issued, _, _ = validate(loan)
    if loan['status'] != 'open':
        raise ValueError('Договор уже закрыт')
    days = (on_date - issued).days
    if days < 0:
        raise ValueError('Дата расчета раньше выдачи')
    interest = min(principal * rate * days, principal * cap)
    interest = interest.quantize(CENT, rounding=ROUND_HALF_UP)
    return {'days': days, 'interest': interest,
            'total': principal + interest}


def select_expired(loans, on_date):
    """Однопроходный отбор. Это список для проверки, а не разрешение продажи."""
    result = []
    seen = set()
    for loan in loans:
        *_, issued, due, grace = validate(loan)
        if loan['id'] in seen:
            raise ValueError('Повтор номера договора')
        seen.add(loan['id'])
        if loan['status'] == 'open' and on_date > grace:
            result.append(loan['id'])
    return result


def redeem(loan, payment, on_date):
    """Полный выкуп. Исходный словарь не изменяется."""
    calculated = quote(loan, on_date)
    paid = number(payment, 'Платеж', CENT, Decimal('200000000'))
    if paid != calculated['total']:
        raise ValueError('Для полного выкупа нужен точный платеж')
    return dict(loan, status='redeemed', closed_on=on_date.isoformat())


def load_loans(path):
    with Path(path).open(encoding='utf-8') as stream:
        loans = json.load(stream)
    if not isinstance(loans, list):
        raise ValueError('Ожидается список договоров')
    return loans


def run_demo(on_date):
    path = Path(__file__).resolve().parents[1] / 'data' / 'loans.json'
    loans = load_loans(path)
    print('РАБОТА ЛОМБАРДА — учебная модель')
    print(f'Дата расчета: {on_date}')
    print('Данные вымышленные; дневная ставка 0.1%, предел процентов 100%.')
    for loan in loans:
        if loan['status'] == 'open':
            calc = quote(loan, on_date)
            print(f"{loan['id']}: дней={calc['days']}; "
                  f"проценты={calc['interest']:.2f}; выкуп={calc['total']:.2f}")
        else:
            print(f"{loan['id']}: закрыт ({loan['status']})")
    expired = select_expired(loans, on_date)
    print('Истек льготный срок: ' + (', '.join(expired) or 'нет'))
    print('Список требует проверки сотрудником; автоматической продажи нет.')
    first = loans[0]
    total = quote(first, on_date)['total']
    closed = redeem(first, total, on_date)
    print(f"Полный выкуп {closed['id']}: платеж={total:.2f}; статус={closed['status']}")
    try:
        redeem(closed, total, on_date)
    except ValueError as error:
        print(f'Повторный выкуп отклонен: {error}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', default='2026-10-05',
                        help='Дата расчета ГГГГ-ММ-ДД')
    args = parser.parse_args()
    try:
        run_demo(date.fromisoformat(args.as_of))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f'Ошибка: {error}\n')


if __name__ == '__main__':
    main()
