from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.blessings import BLESSING_DEFS
from wyrdfall.domain.character import RESOURCE_NAMES
from wyrdfall.domain.consumables import CONSUMABLE_SLOTS
from wyrdfall.domain.content import AREA_NAMES, CLASS_DEFS
from wyrdfall.domain.pacts import PACT_DEFS
from wyrdfall.domain.race_evolution import RACE_EVOLUTION_DEFS
from wyrdfall.domain.specializations import SPECIALIZATION_DEFS, STAGE2_DEFS, evolution_name, evolution_offers
from wyrdfall.domain.wyrd import WYRD_MAX, danger_multiplier, reward_multiplier
from wyrdfall.engine.session import EVOLUTION_LEVEL, EVOLUTION_STAGE2_LEVEL
from wyrdfall.ui.connection_status import ConnectionStatusPanel
from wyrdfall.ui.widgets import ButtonRow, Columns, TitleBar, KeyValue, Panel, bar, labeled_bar
from wyrdfall.ui.party_ready import PartyReadyPanel

_ENTER_LABELS = {
    "rest": "Descansar",
    "event": "Investigar",
    "shop": "Visitar o Vendedor",
    "forge": "Forja de Campo",
}
_ROOM_NAMES = {
    "combat": "Combate",
    "rest": "Sala de Descanso",
    "event": "Evento",
    "shop": "Vendedor",
    "forge": "Forja de Campo",
    "special": "Sala Especial",
}


def _node_glyph(encounter) -> str:
    if encounter.is_boss:
        return "♛"
    if encounter.is_elite:
        return "☠"
    if encounter.room_type == "event":
        return "?"
    if encounter.room_type == "special":
        return "◆"
    if encounter.room_type in ("rest", "shop", "forge"):
        return "◆"
    return "⚔"


class DungeonScreen(Screen):
    """The run's hub between rooms: the Área map on top, the party / the
    current room / the run's numbers side by side, and the character
    actions in one row. Every panel refreshes off the client's updates."""

    CSS = """
    DungeonScreen #map-panel { height: auto; }
    DungeonScreen #hub-columns { height: auto; }
    DungeonScreen #room-panel Button { margin-top: 1; }
    DungeonScreen #character-actions, DungeonScreen #character-actions-2 { height: auto; }
    DungeonScreen #character-actions-2 { margin-top: 1; }
    DungeonScreen #abandon { width: 100%; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield ConnectionStatusPanel()
            yield TitleBar("", id="dungeon-header")
            with Panel("Mapa da Área", id="map-panel"):
                yield Static("", id="area-map")
            with Columns(id="hub-columns"):
                with Panel("Grupo", variant="success", id="party-panel-hub"):
                    yield Static("", id="party-status")
                with Panel("Sala atual", variant="accent", id="room-panel"):
                    yield Static("", id="dungeon-body")
                    yield Static("", id="room-kind")
                    yield Button("Entrar no Encontro", id="enter", variant="primary")
                    yield PartyReadyPanel()
                with Panel("Run", id="run-panel"):
                    yield KeyValue(id="run-status")
            with Panel("Personagem", id="character-panel"):
                with ButtonRow(id="character-actions"):
                    yield Button("Talentos", id="talents")
                    yield Button("Atributos", id="attributes")
                    yield Button("Equipamento", id="equipment")
                    yield Button("Consumíveis", id="consumables")
                with ButtonRow(id="character-actions-2"):
                    yield Button("Cartas", id="cards")
                    yield Button("Contratos", id="contracts")
                    yield Button("Evoluir", id="evolve", disabled=True)
            with ButtonRow(id="gear-row", classes="actions"):
                yield Button("Abandonar Run (Derrota / Menu Principal)", id="abandon")
        yield Footer()

    def on_mount(self) -> None:
        self._entered_combat = False
        self._showing_result = False
        self._subscribed_client = self.app.client
        if self._subscribed_client is None:
            return  # A queued mount may finish after suspend/abandon closed the run.
        self._subscribed_client.on_update(self._queue_update)
        # nested panels may still be mounting when a remote update lands
        # right at push time -- render once the first layout is done
        self.call_after_refresh(self.refresh_dungeon)

    def on_unmount(self) -> None:
        if self._subscribed_client is not None:
            self._subscribed_client.off_update(self._queue_update)

    def _queue_update(self) -> None:
        self.call_later(self.refresh_dungeon)

    def on_screen_resume(self) -> None:
        self.refresh_dungeon()

    # -- rendering -----------------------------------------------------------

    def refresh_dungeon(self) -> None:
        client = self.app.client
        if client is None or getattr(self.app, "_leaving_run", False):
            return  # the run was abandoned; queued refreshes may still arrive
        if client.get_last_summary() is not None:
            if self._entered_combat:
                return  # CombatScreen owns the result transition for its fight
            if not self._showing_result:
                self._showing_result = True
                self.run_worker(self._show_result, group="run-result", exclusive=True)
            return
        if not self.query("#dungeon-body"):
            return  # not composed yet (see on_mount); the next update repaints
        if client.get_combat_state() is not None:
            # An encounter is underway -- started either by this client's own
            # "Enter Encounter" click, or (in co-op) by a teammate's. Either
            # way every client reacts to the state the same way: follow along.
            if not self._entered_combat:
                self._entered_combat = True
                from wyrdfall.ui.screens.combat import CombatScreen

                self.app.push_screen(CombatScreen())
            return
        self._entered_combat = False

        if client.is_dungeon_cleared():
            return  # combat.py drives the transition to the summary screen
        encounter = client.current_encounter()
        run = client.get_run()
        dungeon = client.get_dungeon()
        room_type = client.current_room_type()

        area_name = AREA_NAMES.get(encounter.area_id, dungeon.name)
        area_ids = list(dict.fromkeys(e.area_id for e in dungeon.encounters))
        area_number = area_ids.index(encounter.area_id) + 1 if encounter.area_id in area_ids else 1
        self.query_one("#dungeon-header", TitleBar).update(
            f"{area_name}  ·  Área {area_number}/{len(area_ids)}  ·  Sala {run.encounter_index + 1}/{len(dungeon.encounters)}"
        )
        self._render_map(dungeon, run.encounter_index)

        # sala atual
        self.query_one("#dungeon-body", Static).update(f"[bold]{escape(encounter.name)}[/bold]\n{escape(encounter.flavor_text)}")
        kind = _ROOM_NAMES.get(room_type, room_type)
        if room_type == "combat":
            if encounter.is_boss:
                kind = "[bold red]CHEFE[/bold red]"
            elif encounter.is_elite:
                kind = "[bold yellow]Elite[/bold yellow]"
            kind += f"  ·  {len(encounter.enemy_ids)} inimigo{'s' if len(encounter.enemy_ids) != 1 else ''}"
        self.query_one("#room-kind", Static).update(f"\n{kind}")
        self.query_one("#enter", Button).label = _ENTER_LABELS.get(room_type, "Entrar no Encontro")
        self.query_one("#enter", Button).display = not (room_type == "combat" and client.get_readiness() is not None)
        waiting_for_host = room_type == "combat" and not client.can_decide_for_party
        self.query_one("#enter", Button).disabled = waiting_for_host
        if waiting_for_host:
            self.query_one("#enter", Button).label = "Aguardando o host iniciar"

        # grupo
        self.query_one("#party-status", Static).update(self._party_text(client, run))

        # run
        pact_names = ", ".join(PACT_DEFS[pid].name for pid in run.active_pacts if pid in PACT_DEFS) or "nenhum"
        blessing_names = ", ".join(
            BLESSING_DEFS[bid].name for bid in (run.party[0].blessings if run.party else []) if bid in BLESSING_DEFS
        ) or "nenhuma"
        self.query_one("#run-status", KeyValue).set_rows([
            ("Fragmentos", f"[bold]{run.currency_earned}[/bold]"),
            ("Bolsa", f"{len(run.consumables)}/{CONSUMABLE_SLOTS} consumíveis"),
            ("Wyrd", f"{bar(run.wyrd_meter, WYRD_MAX, width=10, color='magenta')} {run.wyrd_meter:.0f}/{WYRD_MAX:.0f}"),
            ("Perigo", f"×{danger_multiplier(run):.2f}"),
            ("Recompensas", f"×{reward_multiplier(run):.2f}"),
            ("Ascensão", run.ascension_level),
            ("Pactos", pact_names),
            ("Bênçãos", blessing_names),
        ])

        # ações do personagem
        local_id = next(iter(client.local_character_ids()), None)
        local_character = next((c for c in run.party if c.id == local_id), None)
        talent_points = local_character.build.talent_tree.points_available if local_character else 0
        attribute_points = local_character.attribute_points_available if local_character else 0
        self.query_one("#talents", Button).label = f"Talentos ({talent_points})" if talent_points else "Talentos"
        self.query_one("#talents", Button).variant = "success" if talent_points else "default"
        self.query_one("#attributes", Button).label = f"Atributos ({attribute_points})" if attribute_points else "Atributos"
        self.query_one("#attributes", Button).variant = "success" if attribute_points else "default"
        self.query_one("#consumables", Button).label = f"Consumíveis ({len(run.consumables)}/{CONSUMABLE_SLOTS})"
        has_offer = local_character is not None and bool(local_character.card_offer)
        cards = self.query_one("#cards", Button)
        cards.label = "Cartas (oferta!)" if has_offer else "Cartas"
        cards.variant = "success" if has_offer else "default"
        contracts = self.query_one("#contracts", Button)
        contracts.label = "Contratos (oferta!)" if run.contract_offer else "Contratos"
        contracts.variant = "success" if run.contract_offer else "default"
        # Stage 1 at EVOLUTION_LEVEL, Estágio 2 at EVOLUTION_STAGE2_LEVEL
        # (docs/design/05b-classes-roster.md §10) -- one button, one flow.
        required_level = EVOLUTION_LEVEL if local_character is None or local_character.specialization_id is None else EVOLUTION_STAGE2_LEVEL
        can_evolve = (
            local_character is not None
            and local_character.level >= required_level
            and bool(evolution_offers(local_character))
        )
        evolve = self.query_one("#evolve", Button)
        evolve.disabled = not can_evolve
        evolve.variant = "warning" if can_evolve else "default"
        evolve.label = "Evoluir!" if can_evolve else "Evoluir"
        if local_character is not None and not can_evolve:
            if local_character.stage2_specialization_id is not None:
                evolve.label = "Evolução completa"
            elif local_character.specialization_id and not any(
                local_character.specialization_id in stage.from_specializations for stage in STAGE2_DEFS.values()
            ):
                evolve.label = "Caminho completo"
            elif local_character.level < required_level:
                evolve.label = f"Evoluir (nível {required_level})"
            else:
                evolve.label = "Sem evolução elegível"

    def _render_map(self, dungeon, current_index: int) -> None:
        encounters = dungeon.encounters
        current = encounters[current_index] if current_index < len(encounters) else None
        cells = []
        for index, encounter in enumerate(encounters):
            if current is not None and encounter.area_id != current.area_id:
                continue
            glyph = _node_glyph(encounter)
            if index < current_index:
                cells.append(f"[dim]{glyph}[/dim]")
            elif index == current_index:
                cells.append(f"[bold reverse] {glyph} [/bold reverse]")
            else:
                cells.append(glyph)
        legend = "[dim]⚔ combate  ☠ elite  ♛ chefe  ? evento  ◆ especial (descanso / vendedor / forja)[/dim]"
        self.query_one("#area-map", Static).update("  ".join(cells) + "\n" + legend)

    def _party_text(self, client, run) -> str:
        blocks = []
        for character in run.party:
            computed = character.computed_stats(client.ruleset)
            you = " [dim](você)[/dim]" if character.id in client.local_character_ids() else ""
            spec = ""
            if character.stage2_specialization_id and character.stage2_specialization_id in STAGE2_DEFS:
                spec = " · " + evolution_name(STAGE2_DEFS[character.stage2_specialization_id].name, character.evolution_variants)
            elif character.specialization_id and character.specialization_id in SPECIALIZATION_DEFS:
                spec = " · " + evolution_name(SPECIALIZATION_DEFS[character.specialization_id].name, character.evolution_variants)
            down = " [bold red](incapacitado)[/bold red]" if character.is_incapacitated else ""
            lines = [
                f"[bold]{escape(character.name)}[/bold]{you}{down}",
                f"[dim]{CLASS_DEFS[character.class_id].name}{spec} · Nível {character.level}[/dim]",
                labeled_bar("PV", character.current_hp, computed.max_hp, width=12),
                labeled_bar(RESOURCE_NAMES[character.resource_kind][:7], character.current_resource, computed.max_resource, width=12, color="cyan"),
                f"[dim]Slots {len(character.equipped_abilities)}/{character.active_slot_capacity}[/dim]",
            ]
            if character.race_evolution_id and character.race_id in RACE_EVOLUTION_DEFS:
                lines.append(f"[magenta]✦ {RACE_EVOLUTION_DEFS[character.race_id].name}[/magenta]")
            blocks.append("\n".join(lines))
        for companion in run.companions:
            computed = companion.computed_stats(client.ruleset)
            owner = next((c.name for c in run.party if c.id == companion.owner_id), "?")
            state = "" if companion.is_alive else " [dim](caído -- volta no próximo combate)[/dim]"
            blocks.append(
                f"[bold]{escape(companion.name)}[/bold] [dim]Companheiro de {escape(owner)}[/dim]{state}\n"
                + labeled_bar("PV", companion.current_hp, computed.max_hp, width=12)
            )
        return "\n\n".join(blocks)

    # -- interaction ---------------------------------------------------------

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("talents", "attributes", "equipment", "consumables", "cards", "contracts", "evolve") or (
            event.button.id == "enter" and self.app.client.current_room_type() != "combat"
        ):
            await self.app.client.cancel_ready()
        if event.button.id == "talents":
            from wyrdfall.ui.screens.talents import TalentScreen

            self.app.push_screen(TalentScreen())
        elif event.button.id == "attributes":
            from wyrdfall.ui.screens.attributes import AttributeScreen

            self.app.push_screen(AttributeScreen())
        elif event.button.id == "equipment":
            from wyrdfall.ui.screens.equipment import EquipmentScreen

            self.app.push_screen(EquipmentScreen())
        elif event.button.id == "consumables":
            from wyrdfall.ui.screens.consumables import ConsumablesScreen

            self.app.push_screen(ConsumablesScreen())
        elif event.button.id == "cards":
            from wyrdfall.ui.screens.cards import CardsScreen

            self.app.push_screen(CardsScreen())
        elif event.button.id == "contracts":
            from wyrdfall.ui.screens.contracts import ContractsScreen

            self.app.push_screen(ContractsScreen())
        elif event.button.id == "evolve":
            from wyrdfall.ui.screens.evolution import EvolutionScreen

            self.app.push_screen(EvolutionScreen())
        elif event.button.id == "enter":
            room_type = self.app.client.current_room_type()
            if room_type == "rest":
                from wyrdfall.ui.screens.rest import RestScreen

                self.app.push_screen(RestScreen())
                return
            if room_type == "event":
                from wyrdfall.ui.screens.event import EventScreen

                self.app.push_screen(EventScreen())
                return
            if room_type == "shop":
                from wyrdfall.ui.screens.shop import ShopScreen

                self.app.push_screen(ShopScreen())
                return
            if room_type == "forge":
                from wyrdfall.ui.screens.forge import ForgeScreen

                self.app.push_screen(ForgeScreen())
                return
            await self.app.client.start_current_encounter()
            self.app.discover_enemies_in_current_encounter()
            # refresh_dungeon (fired by the client's on_update notification
            # this call triggers) is what actually pushes CombatScreen.
        elif event.button.id == "abandon":
            await self.app.abandon_run()

    async def _show_result(self) -> None:
        client = self.app.client
        if client is None or getattr(self.app, "_leaving_run", False):
            return
        summary = client.get_last_summary()
        if summary is None:
            return
        from wyrdfall.ui.screens.run_summary import RunSummaryScreen
        ecos = self.app.bank_run_reward()
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.push_screen(RunSummaryScreen(summary, ecos))
