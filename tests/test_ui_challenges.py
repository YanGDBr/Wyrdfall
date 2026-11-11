"""The four offensive Minigames de Habilidade screens (docs/design/
11-habilidades.md §9) resolve locally to a 0..1 score, and CombatScreen
puts that score on the Action it submits."""

import random

import pytest
from textual.app import App

from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.challenges import ChallengeDef, ChallengeKind
from wyrdfall.ui.screens.ability_challenge import AbilityChallengeScreen
from wyrdfall.ui.screens.combat import CombatScreen


class _Harness(App):
    """Pushes one AbilityChallengeScreen through push_screen_wait (which
    needs a worker, like CombatScreen does) and keeps the score."""

    def __init__(self, screen: AbilityChallengeScreen):
        super().__init__()
        self._challenge_screen = screen
        self.result: float | None = None

    def on_mount(self) -> None:
        self.run_worker(self._play(), exclusive=True)

    async def _play(self) -> None:
        self.result = await self.push_screen_wait(self._challenge_screen)


def _screen(**challenge_kwargs) -> AbilityChallengeScreen:
    return AbilityChallengeScreen("Teste", ChallengeDef(**challenge_kwargs), rng=random.Random(7))


# Timers keep the message queue busy, so use short explicit pauses rather
# than bare pilot.pause() -- same note as the Parry smoke test.


async def test_timing_scores_one_inside_the_window_and_zero_outside():
    screen = _screen(kind=ChallengeKind.TIMING, duration_seconds=2.0)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        screen._elapsed = 1.0  # cursor at 50% -- inside the 40..60% window
        await pilot.press("space")
        await pilot.pause(0.1)
    assert app.result == 1.0

    screen = _screen(kind=ChallengeKind.TIMING, duration_seconds=5.0)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        await pilot.press("space")  # cursor still at the far left
        await pilot.pause(0.1)
    assert app.result == 0.0


async def test_sequence_gives_partial_credit_for_partially_correct_input():
    screen = _screen(kind=ChallengeKind.SEQUENCE, sequence_length=4, show_seconds=0.05)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert screen._input_open
        expected = list(screen.sequence)
        wrong = "down" if expected[-1] != "down" else "up"
        for key in [*expected[:3], wrong]:
            await pilot.press(key)
        await pilot.pause(0.1)
    assert app.result == pytest.approx(0.75)

    screen = _screen(kind=ChallengeKind.SEQUENCE, sequence_length=3, show_seconds=0.05)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        for key in screen.sequence:
            await pilot.press(key)
        await pilot.pause(0.1)
    assert app.result == 1.0


async def test_channel_resolves_on_timeout_with_the_held_fraction_and_skip_scores_zero():
    screen = _screen(kind=ChallengeKind.CHANNEL, duration_seconds=0.3, tick_seconds=0.02)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        await pilot.press("space")
        await pilot.pause(0.5)
        await pilot.pause(0.1)
    assert app.result is not None and 0.0 <= app.result <= 1.0

    screen = _screen(kind=ChallengeKind.CHANNEL, duration_seconds=10.0)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        await pilot.click("#skip")
        await pilot.pause(0.1)
    assert app.result == 0.0


async def test_precision_scores_one_for_the_flashed_zone_only():
    screen = _screen(kind=ChallengeKind.PRECISION, zone_count=3, flash_seconds=0.05)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        await pilot.press(str(screen.correct_zone + 1))
        await pilot.pause(0.1)
    assert app.result == 1.0

    screen = _screen(kind=ChallengeKind.PRECISION, zone_count=3, flash_seconds=0.05)
    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        await pilot.press(str((screen.correct_zone + 1) % 3 + 1))
        await pilot.pause(0.1)
    assert app.result == 0.0


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    return WyrdfallApp()


async def test_combat_runs_the_minigame_before_submitting_and_the_score_reaches_the_action(app):
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        # hand the hero Titã's signature (Janela de Tempo) directly -- the
        # minigame is what's under test, not the 10 levels to earn it
        hero = app.client.get_run().party[0]
        hero.abilities.append("titanic_blow")
        hero.equipped_abilities = ["titanic_blow"]
        hero.current_resource = 10
        hero.base_stats.speed = 99  # act first, whatever the goblins roll

        submitted = []
        real_submit = app.client.submit_action

        async def spy(action):
            submitted.append(action)
            await real_submit(action)

        app.client.submit_action = spy

        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        await pilot.click("#ability_titanic_blow")
        await pilot.pause()
        target = next(b for b in app.screen.query("#action-bar Button") if (b.id or "").startswith("target_"))
        await pilot.click(f"#{target.id}")
        await pilot.pause(0.1)
        await pilot.pause(0.05)
        assert isinstance(app.screen, AbilityChallengeScreen)
        assert submitted == []  # nothing goes out until the minigame resolves

        await pilot.click("#skip")
        await pilot.pause(0.1)
        await pilot.pause(0.05)
        assert isinstance(app.screen, CombatScreen)
        assert len(submitted) == 1 and submitted[0].ability_id == "titanic_blow"
        assert submitted[0].challenge_score == 0.0
        assert any("Minigame: 0%" in line for line in app.client.get_combat_state().log)
