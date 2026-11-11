from wyrdfall.ui.party_ready import PartyReadyPanel
from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, Collapsible

from wyrdfall.domain.items import ENCHANTMENT_DEFS, EQUIPMENT_DEFS, equipped_item_ids, item_definition, item_enchantments, ENCHANTMENT_SLOTS_BY_RARITY, enchantment_choices
from wyrdfall.domain.runes import RUNE_DEFS
from wyrdfall.engine.session import COMBINE_RUNES_FRAGMENTOS_COST, REROLL_ENCHANTMENT_FRAGMENTOS_COST, SessionError
from wyrdfall.ui.connection_status import ConnectionStatusPanel
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, KeyValue, Panel, Rows, TitleBar


class ForgeScreen(Screen):
    """Forja de Campo (docs/design/08-itens-crafting.md): "um tipo de sala
    do mapa (não todo andar tem uma)" -- one of the three Sala Especial
    outcomes (Fase 7), pushed by DungeonScreen when the current node
    resolved to a forge. Two services: rerolling a single already-
    socketed Encantamento on an equipped item (Fragmentos + 1 material of
    that item's rarity) and combining two copies of a rune into its tier-2
    twin (Fragmentos + 1 material Comum). "Seguir viagem" is what consumes
    the node; "Voltar" just returns to the dungeon without spending it."""

    CSS = """
    ForgeScreen #columns { height: auto; }
    ForgeScreen #columns Panel { height: auto; }
    ForgeScreen #wallet { width: 34; }
    ForgeScreen #services { height: 1fr; }
    ForgeScreen #services Panel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield ConnectionStatusPanel()
            yield TitleBar("Forja de Campo")
            with Columns(id="columns"):
                with Panel("Sua bolsa", id="wallet", variant="accent"):
                    yield KeyValue(id="forge-status")
                with Panel("A forja"):
                    yield Hint(
                        f"Gravar ou rerolar um encantamento: {REROLL_ENCHANTMENT_FRAGMENTOS_COST} Fragmentos + 1 material da raridade do item.\n"
                        f"Combinar 2 runas iguais numa runa II: {COMBINE_RUNES_FRAGMENTOS_COST} Fragmentos + 1 material comum."
                    )
            with VerticalScroll(id="services"):
                with Panel("Gravar e rerolar encantamentos"):
                    yield Rows(id="forge-rows")
                with Panel("Combinar runas"):
                    yield Rows(id="combine-rows")
            yield PartyReadyPanel()
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="done")
                yield Button("Seguir viagem" if self.app.client.can_decide_for_party else "Aguardando o host", id="leave", variant="primary", disabled=not self.app.client.can_decide_for_party)
        yield Footer()

    def on_mount(self) -> None:
        self._expanded_items: set[str] = set()
        self.query_one("#leave", Button).display = self.app.client.get_readiness() is None
        self._encounter_index = self.app.client.get_run().encounter_index
        self._subscribed_client = self.app.client
        self._subscribed_client.on_update(self._queue_update)
        self.call_after_refresh(self.refresh_forge)

    def on_unmount(self) -> None:
        self._subscribed_client.off_update(self._queue_update)

    def _queue_update(self) -> None:
        self.call_later(self.refresh_forge)

    def on_screen_resume(self) -> None:
        self.refresh_forge()

    def _local_character_id(self) -> str:
        return next(iter(self.app.client.local_character_ids()))

    def refresh_forge(self) -> None:
        if self.app.client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        if not self.query("#forge-rows"):
            return
        self.query_one("#leave", Button).display = self.app.client.get_readiness() is None
        if self.app.client.get_run().encounter_index != self._encounter_index:
            # a teammate already moved the run on -- follow the shared state
            if self.app.screen is self:
                self.app.pop_screen()
            return
        # Same exclusive-worker/remove-then-remount pattern as every other
        # dynamic-row screen (equipment.py, talents.py, ...).
        self.run_worker(self._render_forge, exclusive=True, group="forge-rows")

    async def _render_forge(self) -> None:
        client = self.app.client
        if client is None or client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        run = client.get_run()
        hero = next(c for c in run.party if c.id == self._local_character_id())
        operation = str(run.forge_operations)

        materials = [(rarity.value.capitalize(), count) for rarity, count in run.materials.items()]
        self.query_one("#forge-status", KeyValue).set_rows([("Fragmentos", f"[bold]{run.currency_earned}[/bold]"), *(materials or [("Materiais", "nenhum")])])

        container = self.query_one("#forge-rows", Rows)
        groups = list(container.query(Collapsible))
        if groups:
            self._expanded_items = {group.id for group in groups if not group.collapsed}
        await container.remove_children()
        rows = []
        for item_id in equipped_item_ids(hero):
            item = item_definition(run, item_id)
            socketed = item_enchantments(hero, item_id)
            if item is None:
                continue
            rows.append(Static(f"[bold]{escape(item.name)}[/bold] [dim]({item.rarity.value})[/dim]"))
            piece = run.equipment_instances[item_id]
            affordable = run.currency_earned >= REROLL_ENCHANTMENT_FRAGMENTOS_COST and run.materials.get(piece.rarity, 0) >= 1
            for slot_index, enchantment_id in enumerate(socketed):
                name = ENCHANTMENT_DEFS[enchantment_id].name if enchantment_id in ENCHANTMENT_DEFS else enchantment_id
                rows.append(Button(f"  ↻ Rerolar {name}", id=f"reroll_{item_id}__{slot_index}", name=operation, disabled=not affordable))
            if len(socketed) < ENCHANTMENT_SLOTS_BY_RARITY[piece.rarity]:
                choices = []
                for eid, enchantment in ENCHANTMENT_DEFS.items():
                    if eid not in socketed and eid in enchantment_choices(hero):
                        choices.append(Button(f"Gravar {enchantment.name} — {enchantment.description}",
                            id=f"engrave_{item_id}__{eid}", name=operation, disabled=not affordable))
                group_id = f"engrave_options_{item_id}"
                rows.append(Collapsible(*choices, title="Gravar em slot vazio", id=group_id,
                                            collapsed=group_id not in self._expanded_items))
        if not rows:
            rows.append(Static("[dim]Equipe uma peça para gravar ou rerolar encantamentos.[/dim]"))
        await container.mount(*rows)

        combine = self.query_one("#combine-rows", Rows)
        await combine.remove_children()
        # 08-itens-crafting.md: "combinar 2 runas numa runa seguinte"
        for rune_id in sorted(set(run.rune_inventory), key=list(RUNE_DEFS).index):
            rune = RUNE_DEFS.get(rune_id)
            if rune is None or rune.upgrades_to is None or run.rune_inventory.count(rune_id) < 2:
                continue
            upgraded = RUNE_DEFS[rune.upgrades_to]
            combine.mount(Button(f"⚒ 2× {rune.name} → {upgraded.name}", id=f"combine_{rune_id}"))
        if not combine.children:
            combine.mount(Static("[dim]Precisa de duas cópias da mesma runa na bolsa.[/dim]"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "done":
            self.app.pop_screen()
            return
        client = self._subscribed_client
        if self.app.client is not client or client.get_run().encounter_index != self._encounter_index:
            return
        try:
            if button_id == "leave":
                await client.leave_node()
                if self.app.screen is self and client.get_run().encounter_index != self._encounter_index:
                    self.app.pop_screen()
            elif button_id.startswith("combine_"):
                await client.combine_runes(button_id.removeprefix("combine_"))
            elif button_id.startswith("engrave_"):
                if event.button.name != str(client.get_run().forge_operations):
                    raise SessionError("A Forja mudou. Confira a peça e tente novamente.")
                item_id, enchantment_id = button_id.removeprefix("engrave_").split("__", 1)
                await client.socket_enchantment(self._local_character_id(), item_id, enchantment_id)
            elif button_id.startswith("reroll_"):
                if event.button.name != str(client.get_run().forge_operations):
                    raise SessionError("A Forja mudou. Confira o encantamento e tente novamente.")
                item_id, slot_index = button_id.removeprefix("reroll_").split("__", 1)
                await client.reroll_enchantment(self._local_character_id(), item_id, int(slot_index))
        except SessionError as exc:
            self.notify(str(exc), severity="warning")
