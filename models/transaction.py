import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import Column, String, DateTime, Date, Numeric, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("categories.id"), nullable=True, index=True)
    type = Column(String(20), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    account_id = Column(String(36), nullable=True, index=True)
    transaction_date = Column(Date, nullable=False, default=date.today)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="transactions", lazy="selectin")
    category_rel = relationship("Category", back_populates="transactions", lazy="selectin")