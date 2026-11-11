"""The Parry minigame (docs/design/01-mecanicas.md §2.3, 11-habilidades.md
§9): a timing bar the defending player's own client renders and resolves
100% locally -- only the ParryResult travels over the network. Named
SkillChallengeScreen (not ParryScreen) because the design docs describe
this as shared infrastructure -- ChallengeDef itself now lives in
domain/challenges.py, and the offensive minigames (ui/screens/
ability_challenge.py) reuse the same timing bar.

First use of keyboard input (on_key) in this codebase -- every other
screen is button-only. Uses Textual's push_screen_wait so the caller
(CombatScreen) can simply `await` the ParryResult instead of wiring up a
callback.
"""

from __future__ import annotations

from time import monotonic

from textual import events
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Static

from wyrdfall.domain.challenges import ChallengeDef, parry_challenge
from wyrdfall.domain.combat import ParryResult
from wyrdfall.domain.keybindings import effective_bindings


class SkillChallengeScreen(Screen[ParryResult]):
    def __init__(self, defender_name: str, attacker_name: str, challenge: ChallengeDef | None = None):
        super().__init__()
        self.defender_name = defender_name
        self.attacker_name = attacker_name
        self.challenge = challenge or parry_challenge()
        self._elapsed = 0.0
        self._started_at = None
        self._resolved = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="challenge-panel"):
            yield Static(f"{self.attacker_name} ataca {self.defender_name}!", classes="title")
            yield Static(f"Aperte {self._minigame_key().upper()} na janela estreita para aparar (contra-ataque: 35% do Ataque). Errar aumenta o dano recebido em 20%. Recusar recebe o ataque normal.", classes="subtitle")
            yield Static("", id="challenge-bar")
            yield Button("Recusar", id="decline")

    def on_mount(self) -> None:
        self._started_at = monotonic()
        self._render_bar()
        self.set_interval(self.challenge.tick_seconds, self._tick)

    def _tick(self) -> None:
        if self._resolved:
            return
        self._elapsed = monotonic() - self._started_at
        if self._elapsed >= self.challenge.duration_seconds:
            self._finish(ParryResult.FAILURE)  # ran out of time while trying
            return
        self._render_bar()

    def _progress(self) -> float:
        return min(1.0, self._elapsed / self.challenge.duration_seconds)

    def _render_bar(self) -> None:
        width = self.challenge.bar_width
        cursor = min(width - 1, int(self._progress() * width))
        window_start = int(self.challenge.hit_window_start * width)
        window_end = max(window_start + 1, int(self.challenge.hit_window_end * width))
        chars = ["-"] * width
        for i in range(window_start, min(window_end, width)):
            chars[i] = "="
        chars[cursor] = "O"
        # "<"/">" rather than "[]" -- Static.update() treats its argument as
        # Textual markup by default, and "[" starts a markup tag.
        self.query_one("#challenge-bar", Static).update("<" + "".join(chars) + ">")

    def on_key(self, event: events.Key) -> None:
        if event.key == self._minigame_key() and not self._resolved:
            event.stop()
            self._elapsed = monotonic() - self._started_at
            # Judge real time, not a rounded cell or delayed animation tick.
            hit = (self._elapsed < self.challenge.duration_seconds
                   and self.challenge.hit_window_start <= self._progress() < self.challenge.hit_window_end)
            self._finish(ParryResult.SUCCESS if hit else ParryResult.FAILURE)

    def _minigame_key(self) -> str:
        meta = getattr(self.app, "meta", None)
        return effective_bindings(getattr(meta, "keybindings", None)).get("minigame", "space")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "decline":
            self._finish(ParryResult.DECLINED)

    def _finish(self, result: ParryResult) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.dismiss(result)
