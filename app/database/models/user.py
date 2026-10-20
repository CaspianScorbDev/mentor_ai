
from sqlalchemy import BigInteger, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("age >= 0 AND age <= 100", name="age_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), default="User", nullable=False)
    age: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    @validates("age")
    def validate_age(self, key, value):
        if not (0 <= value <= 100):
            raise ValueError(f"Parameter '{key}' must be between 0 and 100. Given: {value}")
        return value
