from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BudgetBase(BaseModel):
    category: str = Field(..., min_length=1, max_length=100, description="Budget category name")
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, description="Budget amount limit")
    period: str = Field(..., description="Budget period: monthly, weekly, yearly")
    description: Optional[str] = Field(None, max_length=500, description="Optional budget description")

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        allowed = {"monthly", "weekly", "yearly"}
        if v.lower() not in allowed:
            raise ValueError(f"Period must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: object) -> object:
        if isinstance(v, (int, float, str)):
            val = Decimal(str(v))
            if val <= 0:
                raise ValueError("Amount must be greater than zero")
            return val
        return v


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    category: Optional[str] = Field(None, min_length=1, max_length=100, description="Budget category name")
    amount: Optional[Decimal] = Field(None, gt=0, max_digits=12, decimal_places=2, description="Budget amount limit")
    period: Optional[str] = Field(None, description="Budget period: monthly, weekly, yearly")
    description: Optional[str] = Field(None, max_length=500, description="Optional budget description")

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"monthly", "weekly", "yearly"}
        if v.lower() not in allowed:
            raise ValueError(f"Period must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, (int, float, str)):
            val = Decimal(str(v))
            if val <= 0:
                raise ValueError("Amount must be greater than zero")
            return val
        return v


class BudgetResponse(BudgetBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    spent: Decimal = Field(default=Decimal("0.00"), description="Total amount spent in this budget category")
    remaining: Decimal = Field(default=Decimal("0.00"), description="Remaining budget amount")
    created_at: datetime
    updated_at: datetime