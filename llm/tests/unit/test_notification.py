"""Тесты форматирования уведомления для Telegram."""

from app.domain.assessment import Assessment
from app.domain.listing import Budget, Listing
from app.domain.notification import MAX_TEXT_LENGTH, build_notification


class TestBuildNotification:
    def test_renders_structure_with_budget(self) -> None:
        listing = Listing(
            id="91668753",
            title="Настроить RAG",
            description="...",
            budget=Budget(raw="до 20 000 ₽", amount=20000, currency="₽", bound="up_to"),
        )
        assessment = Assessment(summary="Поднять RAG над PDF.", suitability_score=88)

        command = build_notification(listing, assessment)

        assert command.parse_mode == "HTML"
        assert '<a href="https://profi.ru/backoffice/n.php?o=91668753">' in command.text
        assert "Настроить RAG" in command.text
        assert "Поднять RAG над PDF." in command.text
        assert "💰 до 20 000 ₽" in command.text
        assert "🎯 Соответствие: 88/100" in command.text

    def test_omits_budget_line_when_absent(self) -> None:
        listing = Listing(id="1", title="t", description="d")
        assessment = Assessment(summary="s", suitability_score=70)

        command = build_notification(listing, assessment)

        assert "💰" not in command.text
        assert "🎯 Соответствие: 70/100" in command.text

    def test_escapes_html_in_title_and_summary(self) -> None:
        listing = Listing(id="1", title="A & B <script>", description="d")
        assessment = Assessment(summary="x < y & z", suitability_score=70)

        command = build_notification(listing, assessment)

        assert "&amp;" in command.text
        assert "&lt;script&gt;" in command.text
        assert "<script>" not in command.text

    def test_truncates_to_telegram_limit(self) -> None:
        listing = Listing(id="1", title="t", description="d")
        assessment = Assessment(summary="я" * 6000, suitability_score=70)

        command = build_notification(listing, assessment)

        assert len(command.text) <= MAX_TEXT_LENGTH
        assert "🎯 Соответствие: 70/100" in command.text

    def test_renders_without_summary_block_when_empty(self) -> None:
        listing = Listing(id="1", title="t", description="d")
        assessment = Assessment(summary="", suitability_score=50)

        command = build_notification(listing, assessment)

        # только заголовок и мета-блок → ровно один разделитель
        assert command.text.count("\n\n") == 1
        assert "🎯 Соответствие: 50/100" in command.text
