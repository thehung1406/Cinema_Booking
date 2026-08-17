from sqlmodel import Session, select
from typing import Optional
from app.models.user import User

class AuthRepository:
    @staticmethod
    def get_user_by_username(session: Session,username: str) -> Optional[User]:
        statement = select(User).where(User.username == username)
        return session.exec(statement).first()

    @staticmethod
    def get_user_by_email(session: Session,email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        return session.exec(statement).first()

    @staticmethod
    def create_user(session: Session,user: User) -> User:
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def get_user(session: Session,user_id: int) -> Optional[User]:
        return session.get(User, user_id)
