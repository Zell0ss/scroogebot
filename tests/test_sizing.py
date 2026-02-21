import pytest
from src.sizing.models import CommissionStructure


def test_fixed_commission():
    c = CommissionStructure(comision_fija=2.0)
    assert c.calcular(500.0) == 2.0
    assert c.calcular(5000.0) == 2.0


def test_pct_commission_no_limits():
    c = CommissionStructure(comision_pct=0.12)
    assert c.calcular(1000.0) == pytest.approx(1.2)


def test_pct_commission_with_minimum():
    c = CommissionStructure(comision_pct=0.12, comision_minima=3.0)
    assert c.calcular(100.0) == 3.0      # 0.12 < 3.0 → floor applies
    assert c.calcular(5000.0) == pytest.approx(6.0)  # 6.0 > 3.0 → no floor


def test_pct_commission_with_maximum():
    c = CommissionStructure(comision_pct=0.12, comision_minima=3.0, comision_maxima=25.0)
    assert c.calcular(30_000.0) == 25.0  # 36.0 > 25.0 → ceiling applies


def test_zero_commission():
    c = CommissionStructure()
    assert c.calcular(10_000.0) == 0.0
