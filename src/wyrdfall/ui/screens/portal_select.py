from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.content import AREA_NAMES, PORTAL_DEFS
from wyrdfall.domain.models import Archetype, DamageElement
from wyrdfall.ui.widgets import ButtonRow, Columns, TitleBar, Hint, Panel


class PortalSelectScreen(Screen):
    """Pushed by ArchetypeSelectScreen's "Continuar" -- the Portal de
    Entrada (docs/design/14-estrutura-da-run.md §1/§3) is the last
    choice before a run starts, because it decides the whole path (in
    order) the run will walk, ending at Área 12 either way."""

    CSS = """
    PortalSelectScreen #portal-rows { height: auto; }
    PortalSelectScreen #portal-rows Panel { height: 16; }
    PortalSelectScreen .path { height: auto; }
    """

    def __init__(
        self, class_id: str, sealed_archetypes: set[Archetype], sealed_elements: set[DamageElement] | None = None,
    ) -> None:
        super().__init__()
        self._class_id = class_id
        self._sealed = sealed_archetypes
        self._sealed_elements = sealed_elements or set()

    def compose(self) -> ComposeResult:
        unlocked = self.app.meta.unlocked_portals
        with Vertical(classes="frame"):
            yield TitleBar("Nova Run -- 2. Escolha o Portal de Entrada")
            yield Hint("O Portal decide o caminho inteiro: as Áreas, em ordem, até o chefe final. Uma coluna por Portal.")
            with Columns(id="portal-rows"):
                for portal in PORTAL_DEFS.values():
                    is_open = portal.id in unlocked
                    with Panel("aberto" if is_open else "bloqueado", variant="accent" if is_open else ""):
                        name = f"[bold]{portal.name}[/bold]" if is_open else f"[dim bold]{portal.name}[/dim bold]"
                        yield Static(name + "\n")
                        path = "\n".join(f"{i + 1}. {AREA_NAMES[a]}" for i, a in enumerate(portal.path))
                        yield Static(path if is_open else f"[dim]{path}[/dim]", classes="path")
                        if is_open:
                            yield Button("Escolher", id=f"portal_{portal.id}", variant="primary")
                        else:
                            yield Static("\n[dim]Desbloqueie na Guilda ou vencendo.[/dim]")
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
        elif button_id.startswith("portal_"):
            from wyrdfall.ui.screens.dungeon import DungeonScreen

            portal_id = button_id.removeprefix("portal_")
            self.app.start_new_run(
                self._class_id, sealed_archetypes=self._sealed, portal_id=portal_id, sealed_elements=self._sealed_elements,
            )
            self.app.pop_screen()
            self.app.pop_screen()
            self.app.push_screen(DungeonScreen())
