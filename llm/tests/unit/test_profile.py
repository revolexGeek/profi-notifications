"""Тесты профиля исполнителя."""

from app.domain.profile import ContractorProfile


class TestContractorProfile:
    def test_minimal_construction_uses_empty_defaults(self) -> None:
        profile = ContractorProfile()
        assert profile.strong_skills == []
        assert profile.minimum_budget is None
        assert profile.maximum_duration_months is None

    def test_holds_provided_fields(self) -> None:
        profile = ContractorProfile(
            strong_skills=["Python", "FastAPI"],
            rejected_projects=["дизайн"],
        )
        assert "FastAPI" in profile.strong_skills
        assert profile.rejected_projects == ["дизайн"]
