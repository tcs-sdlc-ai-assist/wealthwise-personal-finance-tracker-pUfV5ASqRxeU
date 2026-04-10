from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code for the category (e.g., #FF5733)")
    icon: Optional[str] = Field(None, max_length=50, description="Icon identifier for the category")
    is_active: bool = Field(True, description="Whether the category is active")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Category name must not be blank")
        return stripped

    @field_validator("color")
    @classmethod
    def color_must_be_valid_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("Color must be a valid hex color code (e.g., #FF5733)")
        try:
            int(v[1:], 16)
        except ValueError:
            raise ValueError("Color must be a valid hex color code (e.g., #FF5733)")
        return v.upper()


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code for the category")
    icon: Optional[str] = Field(None, max_length=50, description="Icon identifier for the category")
    is_active: Optional[bool] = Field(None, description="Whether the category is active")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Category name must not be blank")
        return stripped

    @field_validator("color")
    @classmethod
    def color_must_be_valid_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("Color must be a valid hex color code (e.g., #FF5733)")
        try:
            int(v[1:], 16)
        except ValueError:
            raise ValueError("Color must be a valid hex color code (e.g., #FF5733)")
        return v.upper()


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique category identifier")
    user_id: str = Field(..., description="ID of the user who owns this category")
    created_at: datetime = Field(..., description="Timestamp when the category was created")
    updated_at: datetime = Field(..., description="Timestamp when the category was last updated")
    transaction_count: Optional[int] = Field(None, description="Number of transactions in this category")