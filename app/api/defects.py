from __future__ import annotations

from fastapi import APIRouter, HTTPException

INACTIVE_DETAIL = (
    "Mängelverwaltung ist in dieser Version nicht aktiviert. "
    "Das Datenbankschema ist vorbereitet, die Funktion folgt in einer späteren Ausbaustufe."
)

router = APIRouter(prefix="/api/defects", tags=["defects"])


def _inactive():
    raise HTTPException(status_code=501, detail=INACTIVE_DETAIL)


@router.get("")
def list_defects():
    _inactive()


@router.post("", status_code=201)
def create_defect():
    _inactive()


@router.get("/{defect_id}")
def get_defect(defect_id: int):
    _inactive()


@router.put("/{defect_id}")
def update_defect(defect_id: int):
    _inactive()


@router.delete("/{defect_id}", status_code=204)
def delete_defect(defect_id: int):
    _inactive()


@router.post("/{defect_id}/photo", status_code=201)
def upload_photo(defect_id: int):
    _inactive()
