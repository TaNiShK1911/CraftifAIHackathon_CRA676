"""
api/zones.py — GET /api/zones
Returns zone definitions from zones.yaml for frontend overlay drawing.
"""
from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()


@router.get("/zones")
def list_zones() -> dict:
    path = settings.zones_yaml_path
    try:
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return {"zones": data.get("zones", [])}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="zones.yaml not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
