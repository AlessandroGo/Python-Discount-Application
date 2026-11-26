"""Smoke test proving the package and test pipeline work."""

from pc_loan_discount import get_version


def test_get_version() -> None:
    assert get_version() == "0.1.0"
