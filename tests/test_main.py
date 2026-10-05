import sys
import unittest
from pathlib import Path
from datetime import date
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from main import quote, select_expired, redeem, validate


def sample(**changes):
    return dict(dict(id='L001', principal='20000.00', daily_rate='0.001',
                     cap_ratio='1', issued='2026-09-01', due='2026-09-15',
                     grace_until='2026-10-15', status='open'), **changes)


class PawnTests(unittest.TestCase):
    def test_regular(self):
        self.assertEqual(quote(sample(), date(2026, 10, 5)),
                         {'days': 34, 'interest': Decimal('680.00'),
                          'total': Decimal('20680.00')})
    def test_zero_days(self):
        self.assertEqual(quote(sample(), date(2026, 9, 1))['interest'], 0)
    def test_before_issue(self):
        with self.assertRaises(ValueError): quote(sample(), date(2026, 8, 31))
    def test_cap(self):
        self.assertEqual(quote(sample(daily_rate='0.01'), date(2027, 1, 1))['total'], 40000)
    def test_half_up(self):
        self.assertEqual(quote(sample(principal='1.00', daily_rate='0.005'),
                               date(2026, 9, 2))['interest'], Decimal('0.01'))
    def test_grace_boundary(self):
        self.assertEqual(select_expired([sample()], date(2026, 10, 15)), [])
    def test_after_grace(self):
        self.assertEqual(select_expired([sample()], date(2026, 10, 16)), ['L001'])
    def test_closed_excluded(self):
        self.assertEqual(select_expired([sample(status='redeemed')], date(2026, 11, 1)), [])
    def test_empty(self):
        self.assertEqual(select_expired([], date(2026, 10, 5)), [])
    def test_duplicate(self):
        with self.assertRaises(ValueError): select_expired([sample(), sample()], date(2026, 10, 5))
    def test_nonfinite(self):
        with self.assertRaises(ValueError): validate(sample(principal='NaN'))
    def test_negative(self):
        with self.assertRaises(ValueError): validate(sample(principal='-1'))
    def test_date_order(self):
        with self.assertRaises(ValueError): validate(sample(due='2026-08-30'))
    def test_payment_and_copy(self):
        original = sample()
        closed = redeem(original, '20680', date(2026, 10, 5))
        self.assertEqual(closed['status'], 'redeemed')
        self.assertEqual(original['status'], 'open')
    def test_wrong_payment(self):
        with self.assertRaises(ValueError): redeem(sample(), '20000', date(2026, 10, 5))
    def test_double_close(self):
        closed = redeem(sample(), '20680', date(2026, 10, 5))
        with self.assertRaises(ValueError): redeem(closed, '20680', date(2026, 10, 5))


if __name__ == '__main__':
    unittest.main()
