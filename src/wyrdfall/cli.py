"""Entry point for `wyrdfall`, `python -m wyrdfall` and the packaged
executable (packaging/wyrdfall.spec).

    wyrdfall                # play
    wyrdfall --version
    wyrdfall --simulate ... # the headless balance bot (wyrdfall.tools.simulate)
    wyrdfall --self-test    # boots the UI headlessly and exits 0 (packaging check)
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version


def _version() -> str:
    try:
        return version("wyrdfall")
    except PackageNotFoundError:  # frozen executable without package metadata
        return "0.1.0"


def _self_test() -> int:
    """Mounts the real app headlessly (Textual's test pilot), opens the
    Tutorial and the Guild, and exits -- proves a frozen build bundled
    every screen. Uses a throwaway save so it never touches the player's."""
    import asyncio
    import tempfile
    from pathlib import Path

    import wyrdfall.persistence.store as store

    with tempfile.TemporaryDirectory() as tmp:
        store.save_db_path = lambda: Path(tmp) / "selftest.db"
        from wyrdfall.app import WyrdfallApp

        async def drive() -> None:
            app = WyrdfallApp()
            async with app.run_test(size=(100, 50)) as pilot:
                await pilot.pause()
                await pilot.click("#tutorial")
                await pilot.pause()
                await pilot.click("#close")
                await pilot.pause()
                await pilot.click("#meta")
                await pilot.pause()

        asyncio.run(drive())
    print("wyrdfall: self-test ok")
    return 0


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--version", "-V"):
        print(f"wyrdfall {_version()}")
        return
    if args and args[0] == "--simulate":
        from wyrdfall.tools.simulate import main as simulate_main

        raise SystemExit(simulate_main(args[1:]))
    if args and args[0] == "--self-test":
        raise SystemExit(_self_test())
    if args and args[0] in ("--help", "-h"):
        print(__doc__.strip())
        return
    from wyrdfall.app import WyrdfallApp

    WyrdfallApp().run()


if __name__ == "__main__":
    main()
