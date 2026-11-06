"""
routes.py — structure.

The full map of this agent's HTTP API. Read this file to see every endpoint.
"""
from fastapi import APIRouter
from app import handlers

router = APIRouter()

router.add_api_route("/health", handlers.health, methods=["GET"])
router.add_api_route("/v1/invoke", handlers.invoke, methods=["POST"])
router.add_api_route("/v1/stream", handlers.stream, methods=["POST"])
router.add_api_route("/v1/agui", handlers.agui, methods=["POST"])
