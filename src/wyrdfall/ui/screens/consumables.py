from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.character import RESOURCE_NAMES
from wyrdfall.domain.consumables import CONSUMABLE_SLOTS
from wyrdfall.domain.content import CONSUMABLE_DEFS
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, Panel, Rows, TitleBar, labeled_bar


class ConsumablesScreen(Screen):
    """The party's potion pouch (docs/design/14-estrutura-da-run.md §6).
    "Usar" drinks one for this client's own character, between fights.
    The pouch is shared, so in co-op it refreshes off every broadcast."""

    CSS = """
    ConsumablesScreen #columns { height: auto; }
    ConsumablesScreen #columns Panel { height: auto; }
    ConsumablesScreen #hero-panel { width: 34; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Consumíveis")
            with Columns(id="columns"):
                with Panel("Você", variant="success", id="hero-panel"):
                    yield Static("", id="consumables-status")
                with Panel("Bolsa do grupo", variant="accent"):
                    yield Hint("", id="pouch-status")
                    yield Rows(id="consumable-rows")
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.app.client.on_update(self.refresh_pouch)
        self.call_after_refresh(self.refresh_pouch)

    def on_unmount(self) -> None:
        self.app.client.off_update(self.refresh_pouch)

    def _local_character(self):
        client = self.app.client
        local_id = next(iter(client.local_character_ids()), None)
        return next((c for c in client.get_run().party if c.id == local_id), None)

    def refresh_pouch(self) -> None:
        if not self.query("#consumable-rows"):
            return
        run = self.app.client.get_run()
        character = self._local_character()
        self.query_one("#pouch-status", Hint).update(
            f"{len(run.consumables)}/{CONSUMABLE_SLOTS} ocupados. Poções e Tomos são compartilhados; usar fora de combate não gasta turno."
        )
        if character is not None:
            computed = character.computed_stats(self.app.client.ruleset)
            self.query_one("#consumables-status", Static).update(
                f"[bold]{escape(character.name)}[/bold]\n"
                + labeled_bar("PV", character.current_hp, computed.max_hp, width=12) + "\n"
                + labeled_bar(RESOURCE_NAMES[character.resource_kind][:7], character.current_resource, computed.max_resource, width=12, color="cyan")
            )
        self.run_worker(self._render_rows(list(run.consumables)), exclusive=True, group="consumable-rows")

    async def _render_rows(self, pouch: list[str]) -> None:
        container = self.query_one("#consumable-rows", Rows)
        await container.remove_children()
        if not pouch:
            container.mount(Static("[dim]A bolsa está vazia -- poções caem de inimigos e são vendidas pelo Vendedor.[/dim]"))
            return
        for index, consumable_id in enumerate(pouch):
            consumable = CONSUMABLE_DEFS[consumable_id]
            verb = "Ler" if consumable.teaches_ability else "Usar"  # a Tomo is read, not drunk
            container.mount(Button(f"{verb} {consumable.name} [dim]-- {escape(consumable.description)}[/dim]", id=f"use_{index}"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
        elif button_id.startswith("use_"):
            character = self._local_character()
            pouch = self.app.client.get_run().consumables
            index = int(button_id.removeprefix("use_"))
            if character is None or index >= len(pouch):
                return
            await self.app.client.use_consumable(character.id, pouch[index])
