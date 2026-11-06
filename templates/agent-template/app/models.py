"""
models.py — data shapes for the HTTP API layer.

These are the request/response types for the FastAPI endpoints in routes.py.
They are separate from agent/state.py which defines internal graph state.
"""
from typing import Any
from pydantic import BaseModel


class InvokeRequest(BaseModel):
    message: str
    thread_id: str | None = None  # pass to continue an existing conversation


class InvokeResponse(BaseModel):
    thread_id: str
    response: str


class StreamRequest(BaseModel):
    message: str
    thread_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
