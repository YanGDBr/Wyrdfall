from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.keybindings import ACTION_LABELS, DEFAULT_KEYBINDINGS, effective_bindings, rebind


class KeybindingsScreen(Screen):
    """Teclas remapeáveis (docs/design/09-roadmap.md decision 7): pick an
    action, press the new key. A key can hold one action at a time -- the
    other one is unbound rather than silently shared."""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="keybindings-panel"):
            yield Static("Teclas", classes="title")
            yield Static("Clique em uma ação e aperte a tecla nova. Esc cancela.", id="keybindings-hint", classes="subtitle")
            yield Vertical(id="keybinding-rows")
            yield Button("Restaurar padrão", id="reset_keys")
            yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._listening: str | None = None
        self.refresh_rows()

    def refresh_rows(self) -> None:
        self.run_worker(self._render_rows(), exclusive=True, group="keybinding-rows")

    async def _render_rows(self) -> None:
        container = self.query_one("#keybinding-rows", Vertical)
        await container.remove_children()
        bindings = effective_bindings(self.app.meta.keybindings)
        for action, label in ACTION_LABELS.items():
            key = bindings.get(action) or "(sem tecla)"
            waiting = " -- aperte a tecla..." if self._listening == action else ""
            container.mount(Button(f"{label}: {key}{waiting}", id=f"bind_{action}"))

    def on_key(self, event: events.Key) -> None:
        if self._listening is None:
            return
        event.stop()
        if event.key != "escape":
            self.app.meta.keybindings = rebind(self.app.meta.keybindings, self._listening, event.key)
            self.app.save_progress()
        self._listening = None
        self.refresh_rows()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("bind_"):
            self._listening = button_id.removeprefix("bind_")
            self.refresh_rows()
        elif button_id == "reset_keys":
            self.app.meta.keybindings = {}
            self.app.save_progress()
            self.refresh_rows()
        elif button_id == "back":
            self.app.pop_screen()
