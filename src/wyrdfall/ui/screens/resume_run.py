from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Static


class ResumeRunScreen(Screen):
    def compose(self) -> ComposeResult:
        snapshot = self.app.saved_checkpoint()
        with Vertical(classes="frame"):
            yield Static("Retomar run salva", classes="title")
            yield Static(f"{snapshot.dungeon.name} · sala {snapshot.run.encounter_index + 1} · {snapshot.mode}")
            if snapshot.mode == "host":
                yield Static("Porta do host (mantenha a anterior para reconexão automática dos convidados):")
                yield Input(value=str(snapshot.port), id="resume-address")
            elif snapshot.mode == "guest":
                yield Static("Endereço do host (atualize se o IP ou a porta mudaram):")
                yield Input(value=snapshot.uri, id="resume-address")
            yield Static("", id="resume-status")
            yield Button("Retomar", id="resume-confirm", variant="primary")
            yield Button("Voltar", id="back")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "resume-confirm":
            address = self.query_one("#resume-address", Input).value.strip() if self.query("#resume-address") else ""
            try:
                await self.app.resume_saved_run(address)
            except (ValueError, OSError) as exc:
                self.query_one("#resume-status", Static).update(str(exc))
