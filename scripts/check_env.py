"""Checks keys and services before (or after) deploying.

    python -m scripts.check_env

Reads .env (or the environment), then verifies: Telegram token, webhook, database connection,
Groq key and models, with one real AI test answer. Secrets are never printed.
"""
import asyncio

from app.services.diag import format_report, run_checks


async def main() -> None:
    from app.db import init_models
    try:
        await init_models()
    except Exception:
        pass  # the database check below reports the real error
    print(format_report(await run_checks()))


if __name__ == "__main__":
    asyncio.run(main())
