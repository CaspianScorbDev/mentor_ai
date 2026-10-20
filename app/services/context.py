from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import context as context_crud
from app.database.models.context import UserContextModel

CONFIGURED_FIELDS = (
    "current_goal",
    "specialization",
    "communication_style",
    "mentor_tone",
    "interests",
)


def is_configured(context: UserContextModel) -> bool:
    return any(getattr(context, field).strip() for field in CONFIGURED_FIELDS)


def build_context_block(context: UserContextModel) -> str:
    user_name = context.user_name.strip()
    language = context.language.strip()
    lines: list[str] = []

    if user_name:
        lines.append(f"User name: {user_name}")
    if context.current_goal.strip():
        lines.append(f"Current goal: {context.current_goal.strip()}")
    if context.specialization.strip():
        lines.append(f"Mentor specialization: {context.specialization.strip()}")
    if context.communication_style.strip():
        lines.append(f"Preferred communication style: {context.communication_style.strip()}")
    if context.mentor_tone.strip():
        lines.append(f"Mentor tone: {context.mentor_tone.strip()}")
    if context.interests.strip():
        lines.append(f"Interests and things to keep in mind: {context.interests.strip()}")
    if language:
        lines.append(f"Always reply in {language}")

    behaviour: list[str] = []
    if context.mentor_mode:
        behaviour.append(
            "be an accountable mentor: give concrete next steps, call out procrastination"
        )
    if context.use_schedule:
        behaviour.append(
            "the user keeps a schedule — refer to today's events when they are relevant"
        )
    if context.use_plans:
        behaviour.append(
            "the user tracks plans and tasks — offer to break goals into steps and check progress"
        )
    if behaviour:
        lines.append("Behaviour: " + "; ".join(behaviour) + ".")

    if not lines:
        return ""
    return "Context about the user:\n" + "\n".join(f"- {line}" for line in lines)


async def load_context_block(session: AsyncSession) -> str:
    context = await context_crud.get_context(session)
    return build_context_block(context)
