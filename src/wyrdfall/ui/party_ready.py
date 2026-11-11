"""Shared cooperative confirmation, also visible while a host selects a room choice."""

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Static


class PartyReadyPanel(Vertical):
    DEFAULT_CSS = "PartyReadyPanel { height: auto; width: 100%; }"

    def compose(self) -> ComposeResult:
        yield Static("", id="ready-status")
        yield Button("Estou pronto", id="party-ready", variant="primary")

    def on_mount(self) -> None:
        self._client = self.app.client
        self._token = None
        self._ready = False
        if self._client is None:
            self.display = False
            return
        self._client.on_update(self._queue_refresh)
        self.refresh_readiness()
        self.call_after_refresh(self.refresh_readiness)

    def on_unmount(self) -> None:
        if self._client is not None:
            self._client.off_update(self._queue_refresh)

    def _queue_refresh(self) -> None:
        self.call_later(self.refresh_readiness)

    def refresh_readiness(self) -> None:
        if not self.is_mounted or self._client is None or self.app.client is not self._client:
            return
        vote = self._client.get_readiness()
        self.display = vote is not None
        if vote is None:
            return
        self._token = vote.token
        self._ready = bool(vote.ready_ids & self._client.local_character_ids())
        party = self._client.get_run().party
        names = "  ·  ".join(
            ("[green]✓[/green] " if c.id in vote.ready_ids else "[yellow]…[/yellow] ") + escape(c.name)
            for c in party
        )
        self.query_one("#ready-status", Static).update(
            f"[bold]{escape(vote.label)}[/bold]  ·  Prontos {len(vote.ready_ids)}/{len(party)}\n{names}"
        )
        button = self.query_one("#party-ready", Button)
        button.label = "Cancelar prontidão" if self._ready else "Estou pronto"
        button.variant = "warning" if self._ready else "primary"
        button.disabled = vote.action is None or self._client.is_paused

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "party-ready":
            return
        event.stop()
        event.button.disabled = True
        try:
            await self._client.set_party_ready(self._token, not self._ready)
        except Exception as exc:
            self.app.notify(str(exc), severity="warning")
        finally:
            self.refresh_readiness()
