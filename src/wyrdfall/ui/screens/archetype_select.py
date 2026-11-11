from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.character import RESOURCE_NAMES
from wyrdfall.domain.content import CLASS_DEFS, build_ruleset
from wyrdfall.domain.models import Archetype, DamageElement
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.domain.sealing import archetype_seal_bonus, element_seal_bonus
from wyrdfall.ui.widgets import ButtonRow, Columns, TitleBar, Hint, KeyValue, Panel, Rows

_ARCHETYPE_NAMES: dict[Archetype, str] = {
    Archetype.GUERREIRO: "Guerreiro",
    Archetype.PATRULHEIRO: "Patrulheiro",
    Archetype.MISTICO: "Místico",
    Archetype.GUARDIAO: "Guardião",
}

CharacterPick = tuple[str, set[Archetype], set[DamageElement]]


class ArchetypeSelectScreen(Screen[CharacterPick | None]):
    """Pushed by MainMenuScreen's 'Nova Run' before start_new_run --
    picking an Arquétipo Base here decides which ClassDef build_hero
    uses (docs/design/05-classes.md §1). A second step lets the player
    seal 0-3 of the other archetypes (Selamentos, docs/design/
    10-sistemas-de-build.md §7 -- "sobrando só 1") before confirming.

    With `pick_only=True` (the co-op lobby, docs/design/14 §1: each
    player picks their own Personagem + Selamentos) it dismisses with
    the pick instead of moving on to the Portal."""

    CSS = """
    ArchetypeSelectScreen #class-rows Button { height: 3; min-height: 3; border: tall $secondary; content-align-horizontal: center; margin-bottom: 0; }
    ArchetypeSelectScreen #class-rows Button.-selected { border: tall $accent; }
    ArchetypeSelectScreen #seal-rows Button { margin-bottom: 0; }
    ArchetypeSelectScreen #details-body { height: auto; }
    """

    def __init__(self, pick_only: bool = False) -> None:
        super().__init__()
        self._pick_only = pick_only

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Nova Run -- 1. Escolha o personagem" if not self._pick_only else "Lobby -- seu personagem")
            with Columns(classes="body fill"):
                with Panel("Arquétipo Base", variant="accent", id="class-panel"):
                    yield Hint("O ponto de partida. A Especialização vem do que você usar na run.")
                    with Rows(id="class-rows"):
                        for class_def in CLASS_DEFS.values():
                            yield Button(class_def.name, id=f"class_{class_def.id}")
                with Panel("Detalhes", id="details-panel"):
                    yield Static("Escolha um Arquétipo à esquerda.", id="details-body")
                with Panel("Selamentos (opcional)", id="seal-panel"):
                    yield Hint("Selar tira o arquétipo/elemento de toda oferta da run e fortalece o resto.")
                    yield Rows(id="seal-rows")
                    yield Static("", id="seal-summary")
                    yield Button("Selar elementos...", id="seal_elements", disabled=True)
            with ButtonRow(id="creation-row", classes="actions"):
                yield Button("Voltar", id="back")
                yield Button("Confirmar" if self._pick_only else "Continuar", id="confirm", variant="primary", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self._class_id: str | None = None
        self._sealed: set[Archetype] = set()
        self._sealed_elements: set[DamageElement] = set()
        self.refresh_rows()

    def refresh_rows(self) -> None:
        self.run_worker(self._render_rows(), exclusive=True, group="archetype-select-rows")

    async def _render_rows(self) -> None:
        for class_def in CLASS_DEFS.values():
            button = self.query_one(f"#class_{class_def.id}", Button)
            button.set_class(class_def.id == self._class_id, "-selected")
            button.variant = "primary" if class_def.id == self._class_id else "default"

        self._render_details()

        seal_container = self.query_one("#seal-rows", Rows)
        await seal_container.remove_children()
        if self._class_id is not None:
            own_archetype = CLASS_DEFS[self._class_id].base_archetype
            for archetype in Archetype:
                if archetype == own_archetype:
                    continue
                sealed = archetype in self._sealed
                label = f"{'▣' if sealed else '▢'} {_ARCHETYPE_NAMES[archetype]}"
                seal_container.mount(Button(label, id=f"seal_{archetype.value}", variant="warning" if sealed else "default"))
        self._render_seal_summary()

    def _render_details(self) -> None:
        body = self.query_one("#details-body", Static)
        if self._class_id is None:
            body.update("Escolha um Arquétipo à esquerda.")
            return
        class_def = CLASS_DEFS[self._class_id]
        ruleset = self.app.ruleset if hasattr(self.app, "ruleset") else build_ruleset()
        stats = class_def.base_stats
        abilities = ", ".join(
            ruleset.abilities[a].name if a in ruleset.abilities else a for a in class_def.starting_abilities
        )
        race = RACE_DEFS.get(getattr(self.app.meta, "active_race_id", "human")) if hasattr(self.app, "meta") else None
        body.update(f"[bold]{class_def.name}[/bold]\n{class_def.description}\n")
        self._mount_details_grid([
            ("Arquétipo", _ARCHETYPE_NAMES[class_def.base_archetype]),
            ("Recurso", RESOURCE_NAMES[class_def.resource_kind]),
            ("PV / Ataque / Defesa", f"{stats.max_hp:.0f} / {stats.attack:.0f} / {stats.defense:.0f}"),
            ("Velocidade", f"{stats.speed:.0f}"),
            ("Habilidades iniciais", abilities),
            ("Raça (Guilda)", race.name if race else "Humano"),
        ])

    def _mount_details_grid(self, rows) -> None:
        panel = self.query_one("#details-panel", Panel)
        existing = panel.query("#details-grid")
        if existing:
            existing.first(KeyValue).set_rows(rows)
        else:
            grid = KeyValue(id="details-grid")
            panel.mount(grid)
            grid.set_rows(rows)

    def _render_seal_summary(self) -> None:
        count_a, count_e = len(self._sealed), len(self._sealed_elements)
        parts = []
        if count_a:
            parts.append(f"+{archetype_seal_bonus(count_a):.0%} dano ({count_a} arquétipo{'s' if count_a > 1 else ''} selado{'s' if count_a > 1 else ''})")
        if count_e:
            parts.append(f"+{element_seal_bonus(count_e):.0%} dano elemental ({count_e} elemento{'s' if count_e > 1 else ''})")
        self.query_one("#seal-summary", Static).update(
            "[green]" + " · ".join(parts) + "[/green]" if parts else "[dim]Nada selado -- todas as opções abertas.[/dim]"
        )
        self.query_one("#seal_elements", Button).label = (
            f"Selar elementos... ({count_e} selado{'s' if count_e != 1 else ''})" if count_e else "Selar elementos..."
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("class_"):
            self._class_id = button_id.removeprefix("class_")
            self._sealed = set()
            self.refresh_rows()
            self.query_one("#confirm", Button).disabled = False
            self.query_one("#seal_elements", Button).disabled = False
        elif button_id == "seal_elements":
            from wyrdfall.ui.screens.element_seal import ElementSealScreen

            def _store(result: set[DamageElement] | None) -> None:
                if result is not None:
                    self._sealed_elements = result
                    self._render_seal_summary()

            self.app.push_screen(ElementSealScreen(self._sealed_elements), _store)
        elif button_id.startswith("seal_"):
            archetype = Archetype(button_id.removeprefix("seal_"))
            if archetype in self._sealed:
                self._sealed.discard(archetype)
            else:
                self._sealed.add(archetype)
            self.refresh_rows()
        elif button_id == "confirm":
            assert self._class_id is not None
            if self._pick_only:
                self.dismiss((self._class_id, set(self._sealed), set(self._sealed_elements)))
                return
            from wyrdfall.ui.screens.portal_select import PortalSelectScreen

            self.app.push_screen(PortalSelectScreen(self._class_id, self._sealed, self._sealed_elements))
        elif button_id == "back":
            if self._pick_only:
                self.dismiss(None)
            else:
                self.app.pop_screen()
