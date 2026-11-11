from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.bestiary import BESTIARY_ENTRIES
from wyrdfall.domain.content import ENEMY_DEFS


class BestiaryScreen(Screen):
    """Read-only Codex of every enemy id the ruleset knows about -- an entry
    shows its name and lore once discovered (see
    WyrdfallApp.discover_enemies_in_current_encounter), and "???" until
    then. Always pushed on top of MetaProgressionScreen; "Voltar" pops back."""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="bestiary-panel"):
            yield Static("Bestiário", classes="title")
            yield Static("", id="bestiary-body")
            yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_bestiary()

    def on_screen_resume(self) -> None:
        self.refresh_bestiary()

    def refresh_bestiary(self) -> None:
        discovered = self.app.meta.discovered_enemies
        lines = []
        for enemy_id, enemy_def in ENEMY_DEFS.items():
            if enemy_id in discovered:
                lore = BESTIARY_ENTRIES.get(enemy_id, "")
                lines.append(f"{enemy_def.name}\n  {lore}")
            else:
                lines.append("???")
        self.query_one("#bestiary-body", Static).update("\n\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
