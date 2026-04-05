from __future__ import annotations

import asyncio
import os
from pathlib import Path

try:
    from pyrogram import Client
except ImportError as exc:  # pragma: no cover - helper script
    raise SystemExit("Install pyrogram and tgcrypto before running this script.") from exc


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


async def main() -> None:
    api_id = os.getenv("PYROGRAM_API_ID")
    api_hash = os.getenv("PYROGRAM_API_HASH")
    if not api_id or not api_hash:
        raise SystemExit("Set PYROGRAM_API_ID and PYROGRAM_API_HASH before running this script.")

    session_name = os.getenv("PYROGRAM_SESSION_NAME", "madrigal_pyrogram")
    workdir = Path(os.getenv("PYROGRAM_WORKDIR", str(Path.cwd() / ".pyrogram")))
    workdir.mkdir(parents=True, exist_ok=True)
    bot_token = os.getenv("PYROGRAM_BOT_TOKEN")

    async with Client(
        name=session_name,
        api_id=int(api_id),
        api_hash=api_hash,
        workdir=str(workdir),
        bot_token=bot_token or None,
    ) as app:
        me = await app.get_me()
        print(f"Authorized as: {getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}".strip())
        print(f"Session file: {workdir / (session_name + '.session')}")

        if _env_flag("PYROGRAM_EXPORT_SESSION_STRING", default=True):
            session_string = await app.export_session_string()
            print("\nPYROGRAM_SESSION_STRING:")
            print(session_string)


if __name__ == "__main__":  # pragma: no cover - helper script
    asyncio.run(main())
