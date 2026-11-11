from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.models import DamageElement
from wyrdfall.domain.sealing import element_seal_bonus
from wyrdfall.domain.specializations import DAMAGE_ELEMENT_NAMES
from wyrdfall.ui.widgets import ButtonRow, Columns, TitleBar, Hint, Panel, Rows


class ElementSealScreen(Screen[set[DamageElement]]):
    """Selamento de elementos (docs/design/10-sistemas-de-build.md §7):
    "qualquer quantidade dos 11" (Físico can't be sealed -- Ataque Básico
    is the guaranteed floor), each +5% damage on the rest, capped at +25%.
    Dismisses with the chosen set back to ArchetypeSelectScreen."""

    CSS = """
    ElementSealScreen #element-seal-rows Button { margin-bottom: 0; }
    ElementSealScreen #element-columns { height: auto; }
    """

    def __init__(self, sealed: set[DamageElement]) -> None:
        super().__init__()
        self._sealed = set(sealed)

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Nova Run -- Selar elementos")
            with Columns(id="element-columns"):
                with Panel("Elementos", variant="accent"):
                    yield Hint("Clique para selar/dessalar. Um elemento selado nunca aparece como oferta na run.")
                    yield Rows(id="element-seal-rows")
                with Panel("Efeito"):
                    yield Static("", id="element-seal-status")
                    yield Hint("\nO bônus vale para todo dano elemental dos elementos que sobraram. Físico não pode ser selado -- o Ataque Básico é o piso garantido.")
            with ButtonRow(classes="actions"):
                yield Button("Confirmar", id="confirm_elements", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_rows()

    def refresh_rows(self) -> None:
        bonus = element_seal_bonus(len(self._sealed))
        self.query_one("#element-seal-status", Static).update(
            f"Selados: [bold]{len(self._sealed)}[/bold]\nBônus: [green]+{bonus:.0%}[/green] de dano elemental (teto +25%)"
        )
        self.run_worker(self._render_rows(), exclusive=True, group="element-seal-rows")

    async def _render_rows(self) -> None:
        container = self.query_one("#element-seal-rows", Rows)
        await container.remove_children()
        for element in DamageElement:
            if element == DamageElement.PHYSICAL:
                continue
            sealed = element in self._sealed
            label = f"{'▣' if sealed else '▢'} {DAMAGE_ELEMENT_NAMES[element]}"
            container.mount(Button(label, id=f"element_{element.value}", variant="warning" if sealed else "default"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("element_"):
            element = DamageElement(button_id.removeprefix("element_"))
            if element in self._sealed:
                self._sealed.discard(element)
            else:
                self._sealed.add(element)
            self.refresh_rows()
        elif button_id == "confirm_elements":
            self.dismiss(set(self._sealed))
