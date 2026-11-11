from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.companions import COMPANION_DEFS
from wyrdfall.domain.conquests import CONQUEST_DEFS
from wyrdfall.domain.content import CLASS_DEFS
from wyrdfall.domain.content.permanent_trees import PERMANENT_TREE_COST, PERMANENT_TREES
from wyrdfall.domain.guild_missions import GUILD_MISSION_DEFS
from wyrdfall.domain.items import Rarity
from wyrdfall.domain.pacts import PACT_DEFS, PACT_SLOT_COST
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.domain.smith import RECIPE_DEFS
from wyrdfall.domain.wyrd import ASCENSION_MAX
from wyrdfall.persistence.store import PARRY_COST
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, KeyValue, Panel, Rows, Tabbed, TitleBar

TABS = [
    ("geral", "Geral"),
    ("racas", "Raças"),
    ("arvores", "Árvores"),
    ("pactos", "Pactos"),
    ("companheiro", "Companheiro"),
    ("ferreiro", "Ferreiro"),
    ("missoes", "Missões"),
    ("opcoes", "Opções"),
]


class MetaProgressionScreen(Screen):
    """The Guild: everything between runs, one tab per system, with the
    Ecos balance always visible on the left."""

    CSS = """
    MetaProgressionScreen #side { width: 30; height: 100%; }
    MetaProgressionScreen #side Panel { height: auto; }
    MetaProgressionScreen #main { width: 1fr; height: 100%; }
    MetaProgressionScreen .pane { height: 100%; }
    MetaProgressionScreen .pane Panel { height: auto; }
    MetaProgressionScreen .pane Button.action { margin-bottom: 0; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Guilda")
            with Columns(classes="body fill"):
                with Vertical(id="side"):
                    with Panel("Tesouro", variant="accent"):
                        yield Static("", id="ecos", classes="big")
                        yield KeyValue(id="profile")
                    with Panel("Runs recentes"):
                        yield Static("", id="history")
                with Vertical(id="main"):
                    tabbed = Tabbed(TABS, initial="geral", id="guild-tabs")
                    tabbed.add_pane("geral", VerticalScroll(
                        Panel("Compras permanentes", Static("", id="meta-body"),
                              Button("Comprar Ponto de Talento Bônus", id="buy", classes="action"),
                              Button("Desbloquear Aparar (Parry)", id="buy_parry", classes="action")),
                        Panel("Ascensão", Hint("", id="ascension-status"), Rows(id="ascension-rows")),
                        Panel("Conquistas", Rows(id="conquest-rows"), Static("", id="conquest-body")),
                        classes="pane",
                    ))
                    tabbed.add_pane("racas", VerticalScroll(
                        Panel("Raças", Hint("A raça ativa entra em toda run nova. Cada uma se desbloqueia de um jeito."), Rows(id="race-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("arvores", VerticalScroll(
                        Panel("Árvores permanentes", Hint(f"Cada nó custa {PERMANENT_TREE_COST} Ecos e nunca desaloca. Valem para a raça ativa e o arquétipo escolhido."), Rows(id="permanent-tree-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("pactos", VerticalScroll(
                        Panel("Pactos do Wyrd", Hint("", id="pact-status"), Button("", id="buy_pact_slot", classes="action"), Rows(id="pact-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("companheiro", VerticalScroll(
                        Panel("Companheiro", Hint("", id="companion-status"), Rows(id="companion-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("ferreiro", VerticalScroll(
                        Panel("Ferreiro", Hint("", id="smith-status"), Rows(id="smith-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("missoes", VerticalScroll(
                        Panel("Quadro de Missões", Static("", id="mission-body")),
                        Panel("Bestiário", Hint("Todo inimigo já encontrado, com sua lore."), Button("Abrir o Bestiário", id="bestiary", classes="action")),
                        classes="pane",
                    ))
                    tabbed.add_pane("opcoes", VerticalScroll(
                        Panel("Acessibilidade",
                              Button("", id="toggle_fast_combat", classes="action"),
                              Button("", id="toggle_palette", classes="action"),
                              Button("Teclas (remapear)", id="keybindings", classes="action")),
                        classes="pane",
                    ))
                    yield tabbed
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.call_after_refresh(self.refresh_meta)

    def on_screen_resume(self) -> None:
        self.refresh_meta()

    def refresh_meta(self) -> None:
        if not self.query("#ecos"):
            return
        meta = self.app.meta
        self.query_one("#ecos", Static).update(f"[bold cyan]{meta.ecos}[/bold cyan] Ecos")
        race = RACE_DEFS.get(meta.active_race_id)
        self.query_one("#profile", KeyValue).set_rows([
            ("Raça ativa", race.name if race else meta.active_race_id),
            ("Melhor andar", meta.best_floor_reached),
            ("Vitórias", meta.total_victories),
            ("Aparar", "sim" if meta.can_parry else "não"),
            ("Talentos bônus", meta.bonus_talent_points),
        ])
        recent = list(reversed(meta.run_history[-6:]))
        history_lines = "\n".join(
            f"{'[green]✓[/green]' if r.victory else '[red]✗[/red]'} {self._class_name(r.class_id)} -- andar {r.floor_reached}"
            for r in recent
        ) or "[dim]Nenhuma run registrada ainda.[/dim]"
        self.query_one("#history", Static).update(history_lines)

        parry_status = "desbloqueado" if meta.can_parry else f"custa {PARRY_COST} Ecos"
        self.query_one("#meta-body", Static).update(
            f"Pontos de talento bônus: [bold]{meta.bonus_talent_points}[/bold] (o próximo custa {meta.cost_for_next_talent_point()} Ecos)\n"
            f"Aparar (Parry): {parry_status}\n"
        )
        self.query_one("#buy", Button).disabled = meta.ecos < meta.cost_for_next_talent_point()
        self.query_one("#buy_parry", Button).disabled = meta.can_parry or meta.ecos < PARRY_COST
        self.query_one("#toggle_fast_combat", Button).label = (
            f"Velocidade de Combate: {'Rápida' if meta.fast_combat else 'Normal'} (clique pra trocar)"
        )
        self.query_one("#toggle_palette", Button).label = (
            f"Paleta: {'Alternativa (alto contraste)' if meta.alt_palette else 'Padrão'} (clique pra trocar)"
        )
        conquest_lines = "\n".join(
            f"{'[green]✓[/green]' if cid in meta.completed_conquests else '[dim]○[/dim]'} [bold]{escape(cdef.name)}[/bold] "
            f"[dim]-- {escape(cdef.description)} ({cdef.ecos_reward} Ecos)[/dim]"
            for cid, cdef in CONQUEST_DEFS.items()
        )
        self.query_one("#conquest-body", Static).update(conquest_lines)
        equipped_vantagens = sum(1 for pid in meta.equipped_pacts if PACT_DEFS[pid].kind == "vantagem")
        self.query_one("#pact-status", Hint).update(
            f"Comprados uma vez com Ecos, equipados livremente antes de cada run. "
            f"Vantagens equipadas: {equipped_vantagens}/{meta.vantagem_slots} slots. "
            f"Pactos de Risco pioram a run em troca de mais Fragmentos/Ecos e sobem o Medidor do Wyrd."
        )
        slot_button = self.query_one("#buy_pact_slot", Button)
        slot_button.label = f"Comprar slot de Vantagem ({PACT_SLOT_COST} Ecos)"
        slot_button.disabled = meta.ecos < PACT_SLOT_COST
        self.query_one("#ascension-status", Hint).update(
            f"Ascensão {meta.ascension_level} ativa. Cada nível: inimigos +15%, recompensas +20%."
            if meta.ascension_unlocked
            else "Bloqueada -- vença uma run pra desbloquear."
        )
        self.run_worker(self._render_races(), exclusive=True, group="race-rows")
        self.run_worker(self._render_permanent_trees(), exclusive=True, group="permanent-tree-rows")
        self.run_worker(self._render_pacts(), exclusive=True, group="pact-rows")
        self.run_worker(self._render_ascension(), exclusive=True, group="ascension-rows")
        active_companion = COMPANION_DEFS.get(meta.active_companion_id or "")
        self.query_one("#companion-status", Hint).update(
            "Um slot próprio, fora dos Slots de Habilidade: luta ao seu lado, age sozinho e volta a cada combate. "
            f"Ativo: {active_companion.name if active_companion else 'nenhum'}."
        )
        self.run_worker(self._render_companions(), exclusive=True, group="companion-rows")
        stash = "  ".join(f"{r.value.capitalize()}: {meta.materials.get(r, 0)}" for r in Rarity)
        self.query_one("#smith-status", Hint).update(
            f"Materiais acumulados entre runs -- {stash}. Cada receita é feita uma vez, com materiais + Ecos."
        )
        self.run_worker(self._render_smith(), exclusive=True, group="smith-rows")
        data = meta.mission_progress_input()
        mission_lines = "\n".join(
            f"{'[green]✓[/green]' if m.id in meta.completed_missions else '[dim]○[/dim]'} [bold]{escape(m.name)}[/bold] "
            f"[dim]-- {escape(m.description)}[/dim] [{min(m.progress(data), m.target)}/{m.target}] {escape(m.reward_text)}"
            for m in GUILD_MISSION_DEFS.values()
        )
        self.query_one("#mission-body", Static).update(mission_lines)

    async def _render_smith(self) -> None:
        meta = self.app.meta
        container = self.query_one("#smith-rows", Rows)
        await container.remove_children()
        for recipe in RECIPE_DEFS.values():
            cost = " + ".join(f"{n} {r.value}" for r, n in recipe.cost_materials.items())
            container.mount(Static(f"[bold]{escape(recipe.name)}[/bold] [dim]-- {escape(recipe.description)} ({cost} + {recipe.cost_ecos} Ecos)[/dim]"))
            if recipe.id in meta.crafted_recipes:
                container.mount(Static("  [green]✓ forjado[/green]"))
            else:
                container.mount(Button(f"  ⚒ Forjar {recipe.name}", id=f"craft_{recipe.id}", disabled=not meta.can_craft(recipe.id)))

    async def _render_companions(self) -> None:
        meta = self.app.meta
        container = self.query_one("#companion-rows", Rows)
        await container.remove_children()
        for companion in COMPANION_DEFS.values():
            stats = companion.base_stats
            active = meta.active_companion_id == companion.id
            container.mount(
                Static(f"[bold]{escape(companion.name)}[/bold]{' [green](ativo)[/green]' if active else ''} [dim]-- {escape(companion.description)} (PV {stats.max_hp:.0f}, Ataque {stats.attack:.0f})[/dim]")
            )
            if companion.id not in meta.unlocked_companions:
                container.mount(
                    Button(
                        f"  Comprar ({companion.cost} Ecos)", id=f"companion_buy_{companion.id}",
                        disabled=meta.ecos < companion.cost,
                    )
                )
            else:
                container.mount(Button("  Levar", id=f"companion_pick_{companion.id}", disabled=active))
        container.mount(Button("Sem companheiro", id="companion_none", disabled=meta.active_companion_id is None))

    async def _render_pacts(self) -> None:
        meta = self.app.meta
        container = self.query_one("#pact-rows", Rows)
        await container.remove_children()
        for pact in PACT_DEFS.values():
            kind = "[green]Vantagem[/green]" if pact.kind == "vantagem" else "[red]Risco[/red]"
            equipped = pact.id in meta.equipped_pacts
            container.mount(Static(f"{kind} [bold]{escape(pact.name)}[/bold]{' ✓' if equipped else ''} [dim]-- {escape(pact.description)}[/dim]"))
            if pact.id not in meta.unlocked_pacts:
                container.mount(
                    Button(f"  Comprar ({pact.cost} Ecos)", id=f"pact_buy_{pact.id}", disabled=meta.ecos < pact.cost)
                )
            elif equipped:
                container.mount(Button("  Desequipar", id=f"pact_toggle_{pact.id}", variant="primary"))
            else:
                container.mount(Button("  Equipar", id=f"pact_toggle_{pact.id}"))

    async def _render_ascension(self) -> None:
        meta = self.app.meta
        container = self.query_one("#ascension-rows", Rows)
        await container.remove_children()
        if not meta.ascension_unlocked:
            return
        for level in range(ASCENSION_MAX + 1):
            label = f"Ascensão {level}" if level else "Sem Ascensão"
            active = level == meta.ascension_level
            container.mount(Button(f"{'▣' if active else '▢'} {label}", id=f"ascension_{level}", disabled=active))

    async def _render_permanent_trees(self) -> None:
        meta = self.app.meta
        container = self.query_one("#permanent-tree-rows", Rows)
        await container.remove_children()
        for tree_id, tree in PERMANENT_TREES.items():
            allocated = meta.permanent_tree_allocated.get(tree_id, set())
            container.mount(Static(f"[bold]{escape(tree.definition.name)}[/bold] [dim]{len(allocated)}/{len(tree.nodes)}[/dim]"))
            for node_id, node in tree.nodes.items():
                if node_id in allocated:
                    container.mount(Static(f"  [green]✓[/green] {escape(node.name)} [dim]-- {escape(node.description)}[/dim]"))
                else:
                    can_afford = meta.ecos >= PERMANENT_TREE_COST
                    can_allocate = tree.can_allocate(node_id, allocated)
                    container.mount(
                        Button(
                            f"  ▢ {node.name} [dim]-- {escape(node.description)}[/dim]",
                            id=f"ptree_{tree_id}__{node_id}",
                            disabled=not (can_afford and can_allocate),
                        )
                    )

    async def _render_races(self) -> None:
        meta = self.app.meta
        container = self.query_one("#race-rows", Rows)
        await container.remove_children()
        for race_id, race_def in RACE_DEFS.items():
            unlocked = race_id in meta.unlocked_races
            active = race_id == meta.active_race_id
            tag = " [green](ativa)[/green]" if active else ("" if unlocked else " [dim](bloqueada)[/dim]")
            container.mount(Static(f"[bold]{escape(race_def.name)}[/bold]{tag} [dim]-- {escape(race_def.description)}[/dim]"))
            if unlocked:
                container.mount(Button("  Selecionar", id=f"race_{race_id}", disabled=active, variant="primary" if active else "default"))
            elif race_def.prestige_cost is not None:
                container.mount(Button(
                    f"  Comprar por {race_def.prestige_cost} Ecos (raças evoluídas: "
                    f"{meta.evolved_race_count()}/{race_def.prestige_evolved_races_required})",
                    id=f"race_buy_{race_id}", disabled=not meta.can_buy_race(race_id),
                ))
            else:
                container.mount(Static(f"  [dim]Como desbloquear: {escape(race_def.unlock_description)}[/dim]"))

    def _class_name(self, class_id: str) -> str:
        class_def = CLASS_DEFS.get(class_id)
        return class_def.name if class_def else class_id

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("tab_"):
            return
        if button_id == "buy":
            if self.app.meta.buy_bonus_talent_point():
                self.app.save_progress()
                self.refresh_meta()
        elif button_id == "buy_parry":
            if self.app.meta.buy_parry():
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("ptree_"):
            tree_id, node_id = button_id.removeprefix("ptree_").split("__", 1)
            if self.app.meta.allocate_permanent_node(tree_id, node_id):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("race_buy_"):
            if self.app.meta.buy_race(button_id.removeprefix("race_buy_")):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("race_"):
            self.app.meta.active_race_id = button_id.removeprefix("race_")
            self.app.save_progress()
            self.refresh_meta()
        elif button_id.startswith("pact_buy_"):
            if self.app.meta.buy_pact(button_id.removeprefix("pact_buy_")):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("pact_toggle_"):
            if self.app.meta.toggle_pact(button_id.removeprefix("pact_toggle_")):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id == "buy_pact_slot":
            if self.app.meta.buy_vantagem_slot():
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("craft_"):
            if self.app.meta.craft(button_id.removeprefix("craft_")):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("companion_buy_"):
            if self.app.meta.buy_companion(button_id.removeprefix("companion_buy_")):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id.startswith("companion_pick_"):
            if self.app.meta.set_active_companion(button_id.removeprefix("companion_pick_")):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id == "companion_none":
            self.app.meta.set_active_companion(None)
            self.app.save_progress()
            self.refresh_meta()
        elif button_id.startswith("ascension_"):
            if self.app.meta.set_ascension_level(int(button_id.removeprefix("ascension_"))):
                self.app.save_progress()
                self.refresh_meta()
        elif button_id == "bestiary":
            from wyrdfall.ui.screens.bestiary import BestiaryScreen

            self.app.push_screen(BestiaryScreen())
        elif button_id == "toggle_fast_combat":
            self.app.meta.fast_combat = not self.app.meta.fast_combat
            self.app.save_progress()
            self.refresh_meta()
        elif button_id == "keybindings":
            from wyrdfall.ui.screens.keybindings import KeybindingsScreen

            self.app.push_screen(KeybindingsScreen())
        elif button_id == "toggle_palette":
            self.app.meta.alt_palette = not self.app.meta.alt_palette
            self.app.save_progress()
            self.app.apply_accessibility_settings()
            self.refresh_meta()
        elif button_id == "back":
            self.app.pop_screen()
