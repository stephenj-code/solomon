"""
models.py — data.

Data shapes that flow through the job. Use Pydantic for validated inputs
and outputs. Plain dataclasses for internal intermediate types.
"""
from pydantic import BaseModel


class Item(BaseModel):
    """Input item to process. Replace with the real shape."""
    id: str
    name: str


class Result(BaseModel):
    """Output produced from one Item. Replace with the real shape."""
    item_id: str
    value: str


# Add more shapes below as needed.
