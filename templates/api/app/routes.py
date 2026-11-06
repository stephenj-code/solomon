"""
routes.py — structure.

All routes registered here. This is the map of the API — read this file
to understand every endpoint the service exposes.

Pattern:
  - /health and /ready are always present (required by Kubernetes)
  - Domain routes live under /v1/
  - Add a new router.add_api_route() line to register a new endpoint
"""
from fastapi import APIRouter

from app import handlers

router = APIRouter()

# --- Infrastructure endpoints (required by Kubernetes probes) ---
router.add_api_route("/health", handlers.health, methods=["GET"])
router.add_api_route("/ready", handlers.ready, methods=["GET"])

# --- Domain endpoints ---
# Add new routes here. Example:
#
# router.add_api_route("/v1/items", handlers.create_item, methods=["POST"])
# router.add_api_route("/v1/items/{item_id}", handlers.get_item, methods=["GET"])
