"""
models.py — data shapes.

Every request body and response body is a Pydantic model defined here.
Handlers import from here. Services return these types.

Pattern:
  - One class per distinct data shape
  - Request models: fields the caller sends
  - Response models: fields the API returns
  - Never return raw dicts from handlers — always a model
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    database: str


# --- Add your domain models below ---
# Example:
#
# class ItemCreate(BaseModel):
#     name: str
#     value: float
#
# class ItemResponse(BaseModel):
#     id: str
#     name: str
#     value: float
#     created_at: datetime
