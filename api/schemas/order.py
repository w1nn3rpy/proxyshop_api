from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ProxyType(str, Enum):
    res = "res"
    def_ = "def"
    nondef = "nondef"


class OrderCreate(BaseModel):

    quantity: int = Field(..., gt=0, le=1000)

    country: str = Field(..., min_length=2, max_length=2)

    type: ProxyType

    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "quantity": 5,
                "country": "US",
                "type": "res",
                "city": "New York",
                "state": "NY",
                "zip": "10001"
            }
        }