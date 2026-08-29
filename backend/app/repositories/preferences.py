from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.user import UserPreference


class PreferencesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: UUID):
        row = self.session.get(UserPreference, user_id)
        return dict(row.scanner_preferences) if row is not None else {}

    def upsert(self, user_id: UUID, scanner_preferences: dict):
        row = self.session.get(UserPreference, user_id)
        if row is None:
            row = UserPreference(user_id=user_id, scanner_preferences=dict(scanner_preferences))
            self.session.add(row)
        else:
            row.scanner_preferences = dict(scanner_preferences)
            row.updated_at = func.current_timestamp()
        self.session.flush()
        self.session.refresh(row)
        return row
