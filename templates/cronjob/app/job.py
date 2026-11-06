"""
job.py — structure.

The steps this job runs, in order. Read this file to understand what the job does.
Add a new step by writing it in steps.py and calling it here.
"""
import logging
from app import steps
from app.config import settings

logger = logging.getLogger(__name__)


async def run() -> None:
    """Main job logic. Steps run in sequence."""
    logger.info("job=%s starting", settings.job_name)

    # Step 1: fetch input
    items = await steps.fetch_input()
    logger.info("fetched %d items", len(items))

    # Step 2: process
    results = await steps.process(items)
    logger.info("processed %d results", len(results))

    # Step 3: write output
    await steps.write_output(results)

    logger.info("job=%s done", settings.job_name)
