from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.content import CLASS_DEFS
from wyrdfall.persistence.store import RunSummary
from wyrdfall.ui.widgets import ButtonRow, Columns, KeyValue, Panel


class RunSummaryScreen(Screen):
    CSS = """
    RunSummaryScreen .frame { height: auto; max-width: 90; }
    RunSummaryScreen #verdict { width: 100%; content-align: center middle; text-align: center; height: 3; }
    RunSummaryScreen #columns { height: auto; }
    RunSummaryScreen #columns Panel { height: auto; }
    """

    def __init__(self, summary: RunSummary, ecos_earned: int = 0):
        super().__init__()
        self.summary = summary
        self.ecos_earned = ecos_earned

    def compose(self) -> ComposeResult:
        victory = self.summary.victory
        color = "green" if victory else "red"
        verdict = "V I T Ó R I A" if victory else "V O C Ê   C A I U"
        class_def = CLASS_DEFS.get(self.summary.class_id)
        class_name = class_def.name if class_def else self.summary.class_id
        meta = getattr(self.app, "meta", None)
        with Vertical(classes="frame"):
            yield Static(f"[bold {color}]{verdict}[/bold {color}]", id="verdict")
            with Columns(id="columns"):
                with Panel("A run", variant="success" if victory else "danger"):
                    yield KeyValue(id="summary-body")
                with Panel("Para a Guilda", variant="accent"):
                    yield Static(
                        f"[bold cyan]+{self.ecos_earned} Ecos[/bold cyan]\n\n"
                        f"[dim]Total: {meta.ecos if meta else '?'} Ecos. Gaste na Guilda -- raças, árvores permanentes, Pactos, Ferreiro.[/dim]"
                    )
            with ButtonRow(classes="actions"):
                yield Button("Voltar ao Menu Principal", id="return", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        class_def = CLASS_DEFS.get(self.summary.class_id)
        self.query_one("#summary-body", KeyValue).set_rows([
            ("Resultado", "Vitória" if self.summary.victory else "Derrota"),
            ("Andar alcançado", self.summary.floor_reached),
            ("Classe", class_def.name if class_def else self.summary.class_id),
        ])

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            await self.app.leave_multiplayer()
            self.app.show_main_menu()
