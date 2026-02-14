"""
Announcement endpoints for the High School Management System API
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=800)
    start_date: Optional[str] = None
    end_date: str


def parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format") from exc


def require_teacher(teacher_username: Optional[str]) -> Dict[str, Any]:
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    return teacher


def serialize_announcement(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title", ""),
        "message": doc.get("message", ""),
        "start_date": doc.get("start_date"),
        "end_date": doc.get("end_date"),
        "created_by": doc.get("created_by")
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return announcements that are active today."""
    today = date.today()
    announcements: List[Dict[str, Any]] = []

    for announcement in announcements_collection.find({}):
        start = parse_date(announcement.get("start_date"), "start_date")
        end = parse_date(announcement.get("end_date"), "end_date")

        if end and end < today:
            continue
        if start and start > today:
            continue

        announcements.append(serialize_announcement(announcement))

    announcements.sort(key=lambda item: item.get("start_date") or "")
    return announcements


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all announcements for management."""
    require_teacher(teacher_username)
    announcements = [serialize_announcement(doc) for doc in announcements_collection.find({})]
    announcements.sort(key=lambda item: item.get("end_date") or "")
    return announcements


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(payload: AnnouncementPayload, teacher_username: Optional[str] = None) -> Dict[str, Any]:
    teacher = require_teacher(teacher_username)
    start = parse_date(payload.start_date, "start_date")
    end = parse_date(payload.end_date, "end_date")

    if end is None:
        raise HTTPException(status_code=400, detail="End date is required")
    if start and end < start:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    announcement_id = uuid4().hex
    doc = {
        "_id": announcement_id,
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "created_by": teacher["username"]
    }

    announcements_collection.insert_one(doc)
    return serialize_announcement(doc)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = None
) -> Dict[str, Any]:
    require_teacher(teacher_username)
    start = parse_date(payload.start_date, "start_date")
    end = parse_date(payload.end_date, "end_date")

    if end is None:
        raise HTTPException(status_code=400, detail="End date is required")
    if start and end < start:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    update_doc = {
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": payload.start_date,
        "end_date": payload.end_date
    }

    result = announcements_collection.update_one({"_id": announcement_id}, {"$set": update_doc})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": announcement_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return serialize_announcement(updated)


@router.delete("/{announcement_id}", response_model=Dict[str, Any])
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = None) -> Dict[str, Any]:
    require_teacher(teacher_username)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted"}
