from datetime import date

from fastapi import APIRouter, status

from app.backend.dependencies import SessionDep
from app.backend.schemas import EventCreate, EventRead, EventUpdate
from app.database.crud import schedule as schedule_crud

router = APIRouter(prefix="/schedule", tags=["schedule"])

EVENT_FIELD_MAP = {
    "date": "event_date",
    "start": "start_minute",
    "duration": "duration_minute",
}


def _event_changes(payload: EventUpdate) -> dict[str, object]:
    raw = payload.model_dump(exclude_unset=True)
    return {EVENT_FIELD_MAP.get(key, key): value for key, value in raw.items()}


@router.get("/events", response_model=list[EventRead])
async def list_events(
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[EventRead]:
    events = await schedule_crud.get_event_list(
        session, start=start, end=end, limit=limit, offset=offset
    )
    return [EventRead.model_validate(event) for event in events]


@router.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, session: SessionDep) -> EventRead:
    event = await schedule_crud.create_event(
        session,
        title=payload.title,
        event_date=payload.date,
        start_minute=payload.start,
        duration_minute=payload.duration,
        category=payload.category,
        detail=payload.detail,
    )
    await session.commit()
    return EventRead.model_validate(event)


@router.get("/events/{event_id}", response_model=EventRead)
async def get_event(event_id: int, session: SessionDep) -> EventRead:
    event = await schedule_crud.get_event(session, event_id)
    return EventRead.model_validate(event)


@router.patch("/events/{event_id}", response_model=EventRead)
async def update_event(event_id: int, payload: EventUpdate, session: SessionDep) -> EventRead:
    event = await schedule_crud.change_event(
        session, event_id, changes=_event_changes(payload)
    )
    await session.commit()
    return EventRead.model_validate(event)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: int, session: SessionDep) -> None:
    await schedule_crud.delete_event(session, event_id)
    await session.commit()
