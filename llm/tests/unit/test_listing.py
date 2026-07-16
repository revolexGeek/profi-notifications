"""Тесты доменной заявки и разбора бюджета."""

from app.domain.listing import Budget, Listing


class TestBudget:
    def test_parses_plain_amount_and_currency(self) -> None:
        budget = Budget.from_price(prefix="до", value="700 ₽", suffix="")
        assert budget is not None
        assert budget.amount == 700
        assert budget.currency == "₽"
        assert budget.bound == "up_to"

    def test_parses_amount_with_thousands_separator(self) -> None:
        budget = Budget.from_price(prefix="до", value="20 000 ₽", suffix="")
        assert budget is not None
        assert budget.amount == 20000

    def test_from_bound(self) -> None:
        budget = Budget.from_price(prefix="от", value="5000", suffix="")
        assert budget is not None
        assert budget.bound == "from"
        assert budget.amount == 5000

    def test_non_numeric_value_keeps_text_without_amount(self) -> None:
        budget = Budget.from_price(prefix="", value="Договорная", suffix="")
        assert budget is not None
        assert budget.amount is None
        assert "Договорная" in budget.raw

    def test_none_when_value_empty(self) -> None:
        assert Budget.from_price(prefix="", value="", suffix="") is None

    def test_raw_joins_parts(self) -> None:
        budget = Budget.from_price(prefix="до", value="700 ₽", suffix="")
        assert budget is not None
        assert budget.raw == "до 700 ₽"


class TestListing:
    def test_url_built_from_id(self) -> None:
        listing = Listing(id="91668753", title="t", description="d")
        assert listing.url == "https://profi.ru/backoffice/n.php?o=91668753"

    def test_defaults(self) -> None:
        listing = Listing(id="1", title="t", description="d")
        assert listing.budget is None
        assert listing.is_remote is False
        assert listing.location is None
        assert listing.client_tags == []
