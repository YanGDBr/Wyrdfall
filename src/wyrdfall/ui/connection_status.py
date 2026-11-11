from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Static


class ConnectionStatusPanel(Vertical):
    DEFAULT_CSS = "ConnectionStatusPanel { height: auto; }"

    def compose(self) -> ComposeResult:
        yield Static("", id="connection-status")
        yield Button("Salvar e sair (retomar depois)", id="save_exit", classes="compact")

    def on_mount(self) -> None:
        self._client = self.app.client
        if self._client is None:
            self.display = False
            return
        self._client.on_update(self._queue)
        self.call_after_refresh(self._refresh)

    def on_unmount(self) -> None:
        if self._client is not None:
            self._client.off_update(self._queue)

    def _queue(self) -> None:
        self.call_later(self._refresh)

    def _refresh(self) -> None:
        if not self.is_mounted or self._client is None or self.app.client is not self._client:
            return
        self.query_one("#connection-status", Static).update(escape(self._client.connection_status))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_exit":
            event.stop()
            try:
                await self.app.suspend_run()
            except OSError as exc:
                self.app.notify(str(exc), severity="error")
