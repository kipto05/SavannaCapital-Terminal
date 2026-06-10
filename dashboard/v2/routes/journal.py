"""dashboard/v2/routes/journal.py — trade journal & annotation CRUD.

Mounts under /api/v2/journal/ via dashboard/v2/app.py.

Endpoints
---------
GET  /annotations          — all annotations, optionally filtered by trade_id
GET  /annotations/{id}     — single annotation
POST /annotations          — create annotation (note, tag, trade_id)
PUT  /annotations/{id}     — update annotation
DELETE /annotations/{id}   — delete annotation
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.models import TradeAnnotation
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# E1 — List annotations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/annotations")
def list_annotations(
    trade_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """GET /api/v2/journal/annotations — all annotations, filtered by trade_id if provided."""
    q = db.query(TradeAnnotation).order_by(TradeAnnotation.created_at.desc())
    if trade_id is not None:
        q = q.filter(TradeAnnotation.trade_id == trade_id)
    return [a.to_dict() for a in q.all()]


# ─────────────────────────────────────────────────────────────────────────────
# E2 — Single annotation
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/annotations/{annotation_id}")
def get_annotation(annotation_id: int, db: Session = Depends(get_db)):
    """GET /api/v2/journal/annotations/{id} — single annotation detail."""
    ann = db.query(TradeAnnotation).filter(TradeAnnotation.id == annotation_id).first()
    if ann is None:
        raise HTTPException(404, f"Annotation {annotation_id} not found")
    return ann.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# E3 — Create annotation
# ─────────────────────────────────────────────────────────────────────────────

class AnnotationCreate:
    """Inline schema — validated manually to avoid Pydantic v2 import overhead."""

    @staticmethod
    def validate(body: dict) -> dict:
        note = body.get("note", "").strip()
        if not note:
            raise ValueError("note is required")
        trade_id = body.get("trade_id")
        if trade_id is not None and not isinstance(trade_id, int):
            raise ValueError("trade_id must be an integer")
        tag = body.get("tag", "").strip() or None
        return {"note": note, "trade_id": trade_id, "tag": tag}


@router.post("/annotations")
def create_annotation(body: dict[str, Any], db: Session = Depends(get_db)):
    """POST /api/v2/journal/annotations — create a new journal entry.

    Body
    ----
    note : str (required) — journal text
    trade_id : int | null — linked trade, or null for general note
    tag : str | null — e.g. "post-mortem", "alpha-factor", "regime-change"
    """
    try:
        data = AnnotationCreate.validate(body)
    except ValueError as exc:
        raise HTTPException(400, detail={"error": str(exc)}) from exc

    ann = TradeAnnotation(
        trade_id=data["trade_id"],
        note=data["note"],
        tag=data["tag"],
    )
    db.add(ann)
    db.flush()
    result = ann.to_dict()
    db.commit()
    log.info(
        "Annotation created: id=%d trade_id=%s tag=%s",
        ann.id,
        ann.trade_id,
        ann.tag,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# E4 — Update annotation
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/annotations/{annotation_id}")
def update_annotation(
    annotation_id: int, body: dict[str, Any], db: Session = Depends(get_db)
):
    """PUT /api/v2/journal/annotations/{id} — update note and/or tag."""
    ann = db.query(TradeAnnotation).filter(TradeAnnotation.id == annotation_id).first()
    if ann is None:
        raise HTTPException(404, f"Annotation {annotation_id} not found")

    if "note" in body:
        note = body["note"]
        if not isinstance(note, str) or not note.strip():
            raise HTTPException(400, detail={"error": "note must be a non-empty string"})
        ann.note = note.strip()
    if "tag" in body:
        ann.tag = body["tag"].strip() or None
    if "trade_id" in body:
        trade_id = body["trade_id"]
        if trade_id is not None and not isinstance(trade_id, int):
            raise HTTPException(400, detail={"error": "trade_id must be an integer or null"})
        ann.trade_id = trade_id

    db.flush()
    db.commit()
    log.info("Annotation updated: id=%d", annotation_id)
    return ann.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# E5 — Delete annotation
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/annotations/{annotation_id}")
def delete_annotation(annotation_id: int, db: Session = Depends(get_db)):
    """DELETE /api/v2/journal/annotations/{id} — remove annotation."""
    ann = db.query(TradeAnnotation).filter(TradeAnnotation.id == annotation_id).first()
    if ann is None:
        raise HTTPException(404, f"Annotation {annotation_id} not found")
    db.delete(ann)
    db.commit()
    log.info("Annotation deleted: id=%d", annotation_id)
    return {"deleted": annotation_id}
