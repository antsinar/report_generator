import uuid
from decimal import Decimal
from enum import StrEnum
from typing import List, Optional

from pydantic import EmailStr, PositiveInt
from pydantic_extra_types.phone_numbers import PhoneNumber
from sqlmodel import Field, Relationship, SQLModel


class CurrencyEnum(StrEnum):
    EUR = "€"
    TRY = "₺"


ORDER_PREFIX = "ORD_"


class Customer(SQLModel, table=True):
    id: Optional[PositiveInt] = Field(default=None, primary_key=True)
    name: str
    surname: str
    contact_email: Optional[EmailStr] = Field(default=None, unique=True)
    contact_phone: Optional[PhoneNumber] = Field(default=None, unique=True)

    orders: List["Order"] = Relationship(back_populates="customer")
    reports: List["Report"] = Relationship(back_populates="customer")


class Order(SQLModel, table=True):
    uid: Optional[PositiveInt] = Field(default=None, primary_key=True)
    initialized: int
    amount: Optional[Decimal] = Field(default=None, max_digits=6, decimal_places=2)
    currency: CurrencyEnum = Field(default=CurrencyEnum.EUR)
    finalized: Optional[int] = Field(default=None)

    customer_id: Optional[PositiveInt] = Field(default=None, foreign_key="customer.id")
    customer: Optional[Customer] = Relationship(back_populates="orders")


class Report(SQLModel, table=True):
    uid: str = Field(default_factory=uuid.uuid4, primary_key=True)

    customer_id: Optional[PositiveInt] = Field(default=None, foreign_key="customer.id")
    customer: Optional[Customer] = Relationship(back_populates="reports")
