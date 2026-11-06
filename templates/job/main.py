"""
Entry point. Run with: python main.py

Kubernetes runs this as a Job pod. When main() returns without exception,
the pod exits 0 (success) and the Job is marked Complete. Any uncaught
exception exits 1 (failure) and Kubernetes retries up to backoffLimit.
"""
import asyncio
import logging
import sys

from app.job import run

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        logging.getLogger(__name__).error("job failed: %s", exc, exc_info=True)
        sys.exit(1)
