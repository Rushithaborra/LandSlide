import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthorityContact
from app.schemas import AuthorityContactIn, AuthorityContactOut
from app.security import require_officer_key

router = APIRouter(
    prefix="/authority-contacts", tags=["authority-contacts"], dependencies=[Depends(require_officer_key)]
)


@router.get("", response_model=list[AuthorityContactOut])
def list_authority_contacts(state: str | None = None, db: Session = Depends(get_db)):
    """The real call-list for app.services.sms_alerts.escalate_critical_alert
    -- previously only addable via a direct DB insert (see
    docs/sms_voice_alert_handover.md's example row). This is what makes that
    feature actually usable by an officer, not just a developer."""
    query = db.query(AuthorityContact)
    if state:
        # A state's own contacts plus the all-states ones (state IS NULL).
        query = query.filter(or_(AuthorityContact.state == state, AuthorityContact.state.is_(None)))
    return query.order_by(AuthorityContact.added_at.desc()).all()


@router.post("", response_model=AuthorityContactOut, status_code=201)
def add_authority_contact(payload: AuthorityContactIn, db: Session = Depends(get_db)):
    contact = AuthorityContact(name=payload.name, role=payload.role, phone_number=payload.phone_number, state=payload.state)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204)
def delete_authority_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    contact = db.get(AuthorityContact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Authority contact not found")
    db.delete(contact)
    db.commit()
