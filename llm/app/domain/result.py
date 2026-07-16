"""Результат оценки заказа — выход llm в сторону сервиса-«мозга».

llm отдаёт «мозгу» вердикт вместе с готовым уведомлением; решение «слать/не
слать» в Telegram и публикацию в очередь `notifications` делает «мозг».
"""

from pydantic import BaseModel, ConfigDict

from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.notification import NotificationCommand, build_notification


class AssessmentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    suitability_score: int
    notification: NotificationCommand


def build_result(listing: Listing, assessment: Assessment) -> AssessmentResult:
    return AssessmentResult(
        order_id=listing.id,
        suitability_score=assessment.suitability_score,
        notification=build_notification(listing, assessment),
    )
