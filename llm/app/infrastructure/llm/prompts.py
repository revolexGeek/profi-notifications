"""Сборка промпта для оценки заказа."""

from app.domain.listing import Listing
from app.domain.profile import ContractorProfile

Message = tuple[str, str]

_SYSTEM = """Ты помощник фрилансера-разработчика. По заказу с доски Profi.ru оцени,
насколько он подходит исполнителю, и заполни структуру строго по схеме.

Профиль исполнителя:
{profile}

Правила:
- detected_skills — какие технологии/навыки реально требует заказ.
- unsupported_hits — те из них, что попадают в «Не поддерживаем».
- is_rejected_type = true, если заказ относится к «Отклоняем» (учебные работы,
  чистый фронтенд, дизайн, накрутка).
- suitability_score (0-100): выше — если заказ ложится на сильные навыки и
  предпочтительные проекты; ниже — если совпадение слабое.
- summary — 1-2 предложения по-русски, суть заказа. Не выдумывай фактов."""


def _profile_block(profile: ContractorProfile) -> str:
    def line(label: str, items: list[str]) -> str:
        return f"- {label}: {', '.join(items) if items else '—'}"

    return "\n".join(
        [
            line("Сильные навыки", profile.strong_skills),
            line("Рабочие навыки", profile.working_skills),
            line("Не поддерживаем", profile.unsupported_skills),
            line("Типы проектов", profile.project_types),
            line("Опыт инфраструктуры", profile.infrastructure_experience),
            line("Опыт интеграций", profile.integrations_experience),
            line("Предпочтительно", profile.preferred_projects),
            line("Отклоняем", profile.rejected_projects),
        ]
    )


def _listing_block(listing: Listing) -> str:
    lines = [f"Заголовок: {listing.title}", f"Описание: {listing.description}"]
    if listing.budget is not None:
        lines.append(f"Бюджет: {listing.budget.raw}")
    if listing.is_remote:
        lines.append("Формат: удалённо")
    if listing.location:
        lines.append(f"Локация: {listing.location}")
    if listing.client_tags:
        lines.append(f"Метки клиента: {', '.join(listing.client_tags)}")
    return "\n".join(lines)


def build_messages(listing: Listing, profile: ContractorProfile) -> list[Message]:
    system = _SYSTEM.format(profile=_profile_block(profile))
    return [("system", system), ("human", _listing_block(listing))]
