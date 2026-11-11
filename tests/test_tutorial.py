"""The Tutorial screen: every page renders, navigation is bounded, and
reading it once turns off the main menu's first-time nudge."""

import pytest

from wyrdfall.app import WyrdfallApp
from wyrdfall.ui.screens.main_menu import MainMenuScreen
from wyrdfall.ui.screens.tutorial import PAGES, TutorialScreen


def test_the_tutorial_covers_every_system_a_new_player_meets():
    text = " ".join(title + " " + body for title, body in PAGES).lower()
    for keyword in ("arquétipo", "selamento", "portal", "postura", "aparar", "minigame", "mana", "fúria",
                    "afinidade", "especializa", "runa", "encantamento", "evento", "descanso", "contrato",
                    "bênção", "wyrd", "guilda", "ecos", "pacto", "ascensão", "ferreiro", "co-op", "incapacitado"):
        assert keyword in text, keyword
    assert len(PAGES) >= 8


@pytest.mark.asyncio
async def test_reading_the_tutorial_clears_the_first_time_nudge(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    app = WyrdfallApp()
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert "Primeira vez" in str(app.screen.query_one("#first-time-hint").content)
        await pilot.click("#tutorial")
        await pilot.pause()
        assert isinstance(app.screen, TutorialScreen)
        assert app.screen.query_one("#prev").disabled
        for _ in range(len(PAGES) - 1):
            await pilot.click("#next")
            await pilot.pause(0.3)  # Textual's Button ignores a second press during its active flash
        assert isinstance(app.screen, TutorialScreen)
        assert str(app.screen.query_one("#next").label) == "Concluir"
        assert PAGES[-1][0] in str(app.screen.query_one("#tutorial-title").content)
        await pilot.click("#prev")
        await pilot.pause(0.3)
        assert PAGES[-2][0] in str(app.screen.query_one("#tutorial-title").content)
        await pilot.click("#close")
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert app.meta.tutorial_seen is True
        assert str(app.screen.query_one("#first-time-hint").content) == ""
