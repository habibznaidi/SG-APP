from sqlalchemy import desc
from sqlalchemy.orm import Session

from . import models, schemas


def get_services(db: Session):
    return db.query(models.Service).all()


def get_service(db: Session, service_id: int):
    return db.query(models.Service).filter(models.Service.id == service_id).first()


def create_service(db: Session, service: schemas.ServiceCreate):
    db_service = models.Service(**service.model_dump())
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    return db_service


def update_service(db: Session, service_id: int, service: schemas.ServiceUpdate):
    db_service = get_service(db, service_id)
    if not db_service:
        return None
    for field, value in service.model_dump(exclude_unset=True).items():
        setattr(db_service, field, value)
    db.commit()
    db.refresh(db_service)
    return db_service


def delete_service(db: Session, service_id: int) -> bool:
    db_service = get_service(db, service_id)
    if not db_service:
        return False
    db.delete(db_service)
    db.commit()
    return True


def create_check(db: Session, service_id: int, status: str, status_code=None, response_time_ms=None, error=None):
    db_check = models.Check(
        service_id=service_id,
        status=status,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error=error,
    )
    db.add(db_check)
    db.commit()
    db.refresh(db_check)
    return db_check


def get_checks(db: Session, service_id: int, limit: int = 50):
    return (
        db.query(models.Check)
        .filter(models.Check.service_id == service_id)
        .order_by(desc(models.Check.checked_at))
        .limit(limit)
        .all()
    )


def get_last_check(db: Session, service_id: int):
    return (
        db.query(models.Check)
        .filter(models.Check.service_id == service_id)
        .order_by(desc(models.Check.checked_at))
        .first()
    )


def get_availability_percent(db: Session, service_id: int):
    """% of checks that were UP, over the full history. None if never checked
    (distinct from 0%, which would wrongly suggest a service that's always down)."""
    total = db.query(models.Check).filter(models.Check.service_id == service_id).count()
    if total == 0:
        return None
    up = (
        db.query(models.Check)
        .filter(models.Check.service_id == service_id, models.Check.status == "UP")
        .count()
    )
    return round((up / total) * 100, 1)
