import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

logger = logging.getLogger("servicepulse")
router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[schemas.ServiceWithLastCheck])
def list_services(db: Session = Depends(get_db)):
    services = crud.get_services(db)
    result = []
    for s in services:
        last_check = crud.get_last_check(db, s.id)
        recent = list(reversed(crud.get_checks(db, s.id, limit=20)))  # oldest -> newest for the sparkline
        item = schemas.ServiceWithLastCheck.model_validate(s)
        item.last_check = schemas.CheckOut.model_validate(last_check) if last_check else None
        item.availability_percent = crud.get_availability_percent(db, s.id)
        item.recent_checks = [schemas.CheckOut.model_validate(c) for c in recent]
        result.append(item)
    return result


@router.post("", response_model=schemas.ServiceOut, status_code=201)
def create_service(service: schemas.ServiceCreate, db: Session = Depends(get_db)):
    return crud.create_service(db, service)


@router.get("/{service_id}", response_model=schemas.ServiceOut)
def get_service(service_id: int, db: Session = Depends(get_db)):
    service = crud.get_service(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put("/{service_id}", response_model=schemas.ServiceOut)
def update_service(service_id: int, service: schemas.ServiceUpdate, db: Session = Depends(get_db)):
    updated = crud.update_service(db, service_id, service)
    if not updated:
        raise HTTPException(status_code=404, detail="Service not found")
    return updated


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, db: Session = Depends(get_db)):
    if not crud.delete_service(db, service_id):
        raise HTTPException(status_code=404, detail="Service not found")


@router.post("/{service_id}/check", response_model=schemas.CheckOut)
def check_service(service_id: int, db: Session = Depends(get_db)):
    """Actively probe the target URL and record the result. This is the
    core 'reliability visibility' feature: every check is persisted, so
    availability/latency history survives restarts."""
    service = crud.get_service(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    start = time.perf_counter()
    try:
        resp = httpx.get(service.url, timeout=5.0, follow_redirects=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "UP" if resp.status_code < 400 else "DOWN"
        check = crud.create_check(
            db, service_id, status=status, status_code=resp.status_code, response_time_ms=elapsed_ms
        )
        logger.info("check service=%s status=%s latency_ms=%.1f", service.name, status, elapsed_ms)
    except httpx.RequestError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        check = crud.create_check(db, service_id, status="DOWN", response_time_ms=elapsed_ms, error=str(exc))
        logger.warning("check service=%s status=DOWN error=%s", service.name, exc)
    return check


@router.get("/{service_id}/checks", response_model=list[schemas.CheckOut])
def check_history(service_id: int, db: Session = Depends(get_db)):
    service = crud.get_service(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return crud.get_checks(db, service_id)
