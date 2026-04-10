from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class TransactionCreate(BaseModel):
    model_config = ConfigDict(strict=False)

    amount: Decimal = Field(..., gt=0, description="Transaction amount, must be positive")
    type: TransactionType = Field(..., description="Transaction type: income, expense, or transfer")
    category: str = Field(..., min_length=1, max_length=100, description="Transaction category")
    description: Optional[str] = Field(None, max_length=500, description="Optional transaction description")
    transaction_date: date = Field(..., description="Date of the transaction")
    account_id: Optional[str] = Field(None, description="Associated account ID")

    @field_validator("amount")
    @classmethod
    def validate_amount_precision(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent is not None and abs(int(v.as_tuple().exponent)) > 2:
            raise ValueError("Amount must have at most 2 decimal places")
        return v

    @field_validator("category")
    @classmethod
    def validate_category_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Category must not be blank")
        return stripped


class TransactionUpdate(BaseModel):
    model_config = ConfigDict(strict=False)

    amount: Optional[Decimal] = Field(None, gt=0, description="Transaction amount, must be positive")
    type: Optional[TransactionType] = Field(None, description="Transaction type")
    category: Optional[str] = Field(None, min_length=1, max_length=100, description="Transaction category")
    description: Optional[str] = Field(None, max_length=500, description="Optional transaction description")
    transaction_date: Optional[date] = Field(None, description="Date of the transaction")
    account_id: Optional[str] = Field(None, description="Associated account ID")

    @field_validator("amount")
    @classmethod
    def validate_amount_precision(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v.as_tuple().exponent is not None and abs(int(v.as_tuple().exponent)) > 2:
            raise ValueError("Amount must have at most 2 decimal places")
        return v

    @field_validator("category")
    @classmethod
    def validate_category_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Category must not be blank")
            return stripped
        return v


class TransactionFilter(BaseModel):
    model_config = ConfigDict(strict=False)

    type: Optional[TransactionType] = Field(None, description="Filter by transaction type")
    category: Optional[str] = Field(None, max_length=100, description="Filter by category")
    date_from: Optional[date] = Field(None, description="Filter transactions from this date (inclusive)")
    date_to: Optional[date] = Field(None, description="Filter transactions up to this date (inclusive)")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum transaction amount")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum transaction amount")
    account_id: Optional[str] = Field(None, description="Filter by account ID")

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        if v is not None and info.data.get("date_from") is not None:
            if v < info.data["date_from"]:
                raise ValueError("date_to must be greater than or equal to date_from")
        return v

    @field_validator("max_amount")
    @classmethod
    def validate_amount_range(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        if v is not None and info.data.get("min_amount") is not None:
            if v < info.data["min_amount"]:
                raise ValueError("max_amount must be greater than or equal to min_amount")
        return v


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: Decimal
    type: TransactionType
    category: str
    description: Optional[str] = None
    transaction_date: date
    account_id: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: datetime