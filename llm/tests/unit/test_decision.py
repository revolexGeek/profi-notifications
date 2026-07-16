"""Тесты доменной политики решения: порог + жёсткие фильтры."""

from app.domain.assessment import Assessment
from app.domain.decision import decide


def _assessment(
    *, score: int = 90, unsupported: list[str] | None = None, rejected: bool = False
) -> Assessment:
    return Assessment(
        summary="s",
        suitability_score=score,
        unsupported_hits=unsupported or [],
        is_rejected_type=rejected,
    )


class TestDecide:
    def test_notifies_when_score_at_threshold(self) -> None:
        decision = decide(_assessment(score=60), threshold=60)
        assert decision.notify is True
        assert decision.reason == "above_threshold"

    def test_skips_when_below_threshold(self) -> None:
        decision = decide(_assessment(score=59), threshold=60)
        assert decision.notify is False
        assert decision.reason == "below_threshold"

    def test_unsupported_hits_block_even_with_max_score(self) -> None:
        decision = decide(_assessment(score=100, unsupported=["PHP"]), threshold=60)
        assert decision.notify is False
        assert decision.reason == "unsupported_or_rejected"

    def test_rejected_type_blocks_even_with_max_score(self) -> None:
        decision = decide(_assessment(score=100, rejected=True), threshold=60)
        assert decision.notify is False
        assert decision.reason == "unsupported_or_rejected"
