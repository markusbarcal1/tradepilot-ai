from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.user import AppUser


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: UUID):
        return self.session.get(AppUser, user_id)

    def create(self, user_id: UUID, *, email: str | None = None, display_name: str | None = None, beta_status: str = "active"):
        user = AppUser(user_id=user_id, email=email, display_name=display_name, beta_status=beta_status)
        self.session.add(user)
        self.session.flush()
        return user

    def set_beta_status(self, user_id: UUID, beta_status: str):
        user = self.get(user_id)
        if user is None:
            return None
        user.beta_status = beta_status
        user.updated_at = func.current_timestamp()
        self.session.flush()
        self.session.refresh(user)
        return user
