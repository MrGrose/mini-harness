from src.calculator import total_with_discount


def test_total_with_discount() -> None:
    assert total_with_discount(100, 0.2) == 80
