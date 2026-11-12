from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Area, Category

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
def meta(db: Session = Depends(get_db)):
    areas = db.query(Area).order_by(Area.sort_order).all()
    categories = db.query(Category).order_by(Category.name).all()
    return {
        "app_name": config.APP_NAME,
        "version": config.VERSION,
        "app_url": config.APP_URL,
        "push_enabled": config.PUSH_ENABLED,
        "areas": [{"slug": a.slug, "name": a.name} for a in areas],
        "categories": [
            {"slug": c.slug, "name": c.name, "area_id": c.area_id} for c in categories
        ],
    }
