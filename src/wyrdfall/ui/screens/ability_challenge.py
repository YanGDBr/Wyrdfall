"""Offensive Minigames de Habilidade (docs/design/11-habilidades.md §9):
Janela de Tempo, Sequência, Canalização and Precisão, one screen
dispatching on ChallengeDef.kind. Like the Parry screen it renders and
resolves 100% locally and only the score (0.0..1.0) leaves -- CombatScreen
puts it on the Action it submits, and CombatEngine.resolve turns it into
an effect multiplier (never zero: "errar reduz, nunca zera").

"Pular" is always available and scores 0 -- the floor, same as the
"Recusar -- sempre seguro" on Parry.
"""

from __future__ import annotations

import math
import random

from textual import events
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Static

from wyrdfall.domain.challenges import ChallengeDef, ChallengeKind
from wyrdfall.domain.keybindings import effective_bindings

ARROW_KEYS = ["up", "down", "left", "right"]
ARROW_GLYPHS = {"up": "^", "down": "v", "left": "<", "right": ">"}
# Sequência: how long the player has to repeat it once it's hidden;
# Precisão: how long after the flash before the shot resolves unaided.
_INPUT_WINDOW_SECONDS = 6.0
# Canalização: the marker slides left every tick, Space pushes it right;
# the good zone swings across the bar on a slow sine.
_CHANNEL_DRIFT = 0.02
_CHANNEL_PUSH = 0.08
_CHANNEL_ZONE_HALF_WIDTH = 0.12

_INSTRUCTIONS = {
    ChallengeKind.TIMING: "Aperte Espaço na janela certa.",
    ChallengeKind.SEQUENCE: "Memorize a sequência de setas e repita quando ela sumir.",
    ChallengeKind.CHANNEL: "Aperte Espaço pra manter o marcador dentro da zona enquanto ela se move.",
    ChallengeKind.PRECISION: "Uma zona vai piscar -- aperte o número dela.",
}


class AbilityChallengeScreen(Screen[float]):
    def __init__(self, ability_name: str, challenge: ChallengeDef, rng: random.Random | None = None):
        super().__init__()
        self.ability_name = ability_name
        self.challenge = challenge
        self.rng = rng or random.Random()
        self._elapsed = 0.0
        self._resolved = False
        # sequence
        self.sequence: list[str] = [self.rng.choice(ARROW_KEYS) for _ in range(challenge.sequence_length)]
        self.inputs: list[str] = []
        self._input_open = False
        # channel
        self._position = 0.5
        self._ticks = 0
        self._ticks_in_zone = 0
        # precision
        self.correct_zone = self.rng.randrange(max(1, challenge.zone_count))
        self._flash_visible = True

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="challenge-panel"):
            yield Static(f"{self.ability_name}", classes="title")
            yield Static(_INSTRUCTIONS[self.challenge.kind], classes="subtitle")
            yield Static("", id="challenge-bar")
            yield Static("", id="challenge-prompt")
            yield Button("Pular", id="skip")

    def on_mount(self) -> None:
        kind = self.challenge.kind
        if kind == ChallengeKind.TIMING:
            self._render_timing()
            self.set_interval(self.challenge.tick_seconds, self._tick_timing)
        elif kind == ChallengeKind.SEQUENCE:
            self._render_sequence(show=True)
            self.set_timer(self.challenge.show_seconds, self._open_sequence_input)
        elif kind == ChallengeKind.CHANNEL:
            self._render_channel()
            self.set_interval(self.challenge.tick_seconds, self._tick_channel)
        elif kind == ChallengeKind.PRECISION:
            self._render_precision()
            self.set_timer(self.challenge.flash_seconds, self._hide_flash)
            self.set_timer(self.challenge.flash_seconds + _INPUT_WINDOW_SECONDS, lambda: self._finish(0.0))

    # -- timing (the Parry bar, on offense) ----------------------------------

    def _tick_timing(self) -> None:
        if self._resolved:
            return
        self._elapsed += self.challenge.tick_seconds
        if self._elapsed >= self.challenge.duration_seconds:
            self._finish(0.0)
            return
        self._render_timing()

    def _timing_cursor(self) -> int:
        progress = min(1.0, self._elapsed / self.challenge.duration_seconds)
        return min(self.challenge.bar_width - 1, int(progress * self.challenge.bar_width))

    def _timing_window(self) -> tuple[int, int]:
        width = self.challenge.bar_width
        start = int(self.challenge.hit_window_start * width)
        end = max(start + 1, int(self.challenge.hit_window_end * width))
        return start, min(end, width)

    def _render_timing(self) -> None:
        chars = ["-"] * self.challenge.bar_width
        start, end = self._timing_window()
        for i in range(start, end):
            chars[i] = "="
        chars[self._timing_cursor()] = "O"
        self.query_one("#challenge-bar", Static).update("<" + "".join(chars) + ">")

    def _resolve_timing(self) -> None:
        start, end = self._timing_window()
        self._finish(1.0 if start <= self._timing_cursor() < end else 0.0)

    # -- sequence -------------------------------------------------------------

    def _render_sequence(self, show: bool) -> None:
        if show:
            shown = "  ".join(ARROW_GLYPHS[key] for key in self.sequence)
            self.query_one("#challenge-bar", Static).update(f"Sequência: {shown}")
            self.query_one("#challenge-prompt", Static).update("Memorize...")
        else:
            typed = "  ".join(ARROW_GLYPHS[key] for key in self.inputs)
            blanks = "  ".join("_" for _ in range(len(self.sequence) - len(self.inputs)))
            self.query_one("#challenge-bar", Static).update(f"Repita: {typed}{'  ' if typed and blanks else ''}{blanks}")
            self.query_one("#challenge-prompt", Static).update("Use as setas do teclado.")

    def _open_sequence_input(self) -> None:
        if self._resolved:
            return
        self._input_open = True
        self._render_sequence(show=False)
        self.set_timer(_INPUT_WINDOW_SECONDS, self._resolve_sequence)

    def _resolve_sequence(self) -> None:
        correct = sum(1 for typed, expected in zip(self.inputs, self.sequence) if typed == expected)
        self._finish(correct / max(1, len(self.sequence)))

    # -- channel --------------------------------------------------------------

    def _zone_center(self) -> float:
        return 0.5 + 0.3 * math.sin(self._elapsed * 1.5)

    def _tick_channel(self) -> None:
        if self._resolved:
            return
        self._elapsed += self.challenge.tick_seconds
        self._position = max(0.0, self._position - _CHANNEL_DRIFT)
        self._ticks += 1
        if abs(self._position - self._zone_center()) <= _CHANNEL_ZONE_HALF_WIDTH:
            self._ticks_in_zone += 1
        if self._elapsed >= self.challenge.duration_seconds:
            self._finish(self._ticks_in_zone / max(1, self._ticks))
            return
        self._render_channel()

    def _render_channel(self) -> None:
        width = self.challenge.bar_width
        chars = ["-"] * width
        center = self._zone_center()
        for i in range(width):
            if abs(i / width - center) <= _CHANNEL_ZONE_HALF_WIDTH:
                chars[i] = "="
        chars[min(width - 1, int(self._position * width))] = "O"
        remaining = max(0.0, self.challenge.duration_seconds - self._elapsed)
        self.query_one("#challenge-bar", Static).update("<" + "".join(chars) + ">")
        self.query_one("#challenge-prompt", Static).update(f"Canalizando... {remaining:.1f}s")

    # -- precision ------------------------------------------------------------

    def _render_precision(self) -> None:
        zones = []
        for i in range(self.challenge.zone_count):
            marker = "*" if self._flash_visible and i == self.correct_zone else " "
            zones.append(f"({i + 1}{marker})")
        self.query_one("#challenge-bar", Static).update("   ".join(zones))
        self.query_one("#challenge-prompt", Static).update(
            "Olhe bem..." if self._flash_visible else "Qual era? Aperte o número."
        )

    def _hide_flash(self) -> None:
        if self._resolved:
            return
        self._flash_visible = False
        self._render_precision()

    # -- input ----------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if self._resolved:
            return
        kind = self.challenge.kind
        minigame_key = self._minigame_key()
        if kind == ChallengeKind.TIMING and event.key == minigame_key:
            event.stop()
            self._resolve_timing()
        elif kind == ChallengeKind.CHANNEL and event.key == minigame_key:
            event.stop()
            self._position = min(1.0, self._position + _CHANNEL_PUSH)
        elif kind == ChallengeKind.SEQUENCE and event.key in ARROW_KEYS and self._input_open:
            event.stop()
            self.inputs.append(event.key)
            if len(self.inputs) >= len(self.sequence):
                self._resolve_sequence()
            else:
                self._render_sequence(show=False)
        elif kind == ChallengeKind.PRECISION and event.key.isdigit():
            picked = int(event.key) - 1
            if 0 <= picked < self.challenge.zone_count:
                event.stop()
                self._finish(1.0 if picked == self.correct_zone else 0.0)

    def _minigame_key(self) -> str:
        meta = getattr(self.app, "meta", None)
        return effective_bindings(getattr(meta, "keybindings", None)).get("minigame", "space")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "skip":
            self._finish(0.0)

    def _finish(self, score: float) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.dismiss(max(0.0, min(1.0, score)))
