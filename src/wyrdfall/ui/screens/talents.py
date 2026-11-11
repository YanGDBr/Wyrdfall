from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES
from wyrdfall.engine.session import _talent_tree_id_for
from wyrdfall.ui.screens.equipment import stat_rows
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, KeyValue, Panel, Rows, TitleBar


class TalentScreen(Screen):
    """Always pushed on top of the DungeonScreen -- 'Concluído' just pops back.
    Three boxes: what can be taken now, what is already taken, and what
    is still locked (with its prerequisites), plus live stats on the side."""

    CSS = """
    TalentScreen #side { width: 32; height: 100%; }
    TalentScreen #side Panel { height: auto; }
    TalentScreen #main { width: 1fr; height: 100%; }
    TalentScreen #main Panel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("", id="talent-header")
            with Columns(classes="body fill"):
                with Vertical(id="side"):
                    with Panel("Pontos", variant="accent"):
                        yield Static("", id="talent-points", classes="big")
                        yield Hint("Um nó alocado nunca desaloca. Nós-chave (★) liberam uma habilidade.")
                    with Panel("Atributos de combate"):
                        yield KeyValue(id="stats")
                with VerticalScroll(id="main"):
                    with Panel("Disponíveis agora", variant="success", id="available-panel"):
                        yield Rows(id="talent-buttons")
                    with Panel("Alocados", id="allocated-panel"):
                        yield Rows(id="allocated-rows")
                    with Panel("Bloqueados", id="locked-panel"):
                        yield Hint("Exigem um pré-requisito alocado (ou mais pontos).")
                        yield Rows(id="locked-rows")
            with ButtonRow(classes="actions"):
                yield Button("Concluído", id="done", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.app.client.on_update(self.refresh_talents)
        self.call_after_refresh(self.handle_update)

    def on_unmount(self) -> None:
        self.app.client.off_update(self.refresh_talents)

    def on_screen_resume(self) -> None:
        self.handle_update()

    def _local_character_id(self) -> str:
        return next(iter(self.app.client.local_character_ids()))

    def refresh_talents(self) -> None:
        self.handle_update()

    def handle_update(self) -> None:
        if not self.query("#talent-buttons"):
            return
        # Rebuilding the node list removes and re-mounts buttons, which are
        # async operations in Textual -- coalesce through an exclusive
        # worker so a superseded render is cancelled instead of racing a
        # remove/mount against the next one (see CombatScreen for the same
        # pattern, and the bug it fixes).
        self.run_worker(self._render_talents(), exclusive=True, group="talent-buttons")

    async def _render_talents(self) -> None:
        client = self.app.client
        character_id = self._local_character_id()
        hero = next(c for c in client.get_run().party if c.id == character_id)
        class_def = CLASS_DEFS[hero.class_id]
        # the tree the session allocates on: the evolved branch grafted onto
        # the base tree once a Especialização is picked
        tree = TALENT_TREES.get(_talent_tree_id_for(hero) or "") or TALENT_TREES[class_def.talent_tree_id]
        state = hero.build.talent_tree

        self.query_one("#talent-header", TitleBar).update(f"Talentos -- {hero.name} ({class_def.name}) -- {tree.definition.name}")
        points = state.points_available
        self.query_one("#talent-points", Static).update(
            f"[bold {'green' if points else 'dim'}]{points}[/bold {'green' if points else 'dim'}] ponto{'s' if points != 1 else ''} para gastar"
        )
        self.query_one("#stats", KeyValue).set_rows(stat_rows(hero, client.ruleset))

        available = self.query_one("#talent-buttons", Rows)
        allocated_rows = self.query_one("#allocated-rows", Rows)
        locked_rows = self.query_one("#locked-rows", Rows)
        await available.remove_children()
        await allocated_rows.remove_children()
        await locked_rows.remove_children()
        for node in tree.definition.nodes:
            key = " ★" if node.is_keystone else ""
            cost = f"[dim]({node.cost} pt{'s' if node.cost != 1 else ''})[/dim]"
            text = f"{escape(node.name)}{key} {cost} [dim]-- {escape(node.description)}[/dim]"
            if node.id in state.allocated:
                allocated_rows.mount(Static(f"  ✓ {text}"))
                continue
            reachable = tree.can_allocate(node.id, state.allocated)
            if reachable and node.cost <= state.points_available:
                available.mount(Button(f"▢ {text}", id=f"talent_{node.id}"))
            elif reachable:
                available.mount(Button(f"▢ {text}", id=f"talent_{node.id}", disabled=True))
            else:
                prerequisites = [tree.nodes[p].name for p in tree.graph.predecessors(node.id) if p in tree.nodes]
                needs = f" [dim]← {', '.join(escape(p) for p in prerequisites)}[/dim]" if prerequisites else ""
                locked_rows.mount(Static(f"  · {text}{needs}"))
        if not available.children:
            available.mount(Static("[dim]Nada disponível -- ganhe pontos vencendo combates ou meditando.[/dim]"))
        if not allocated_rows.children:
            allocated_rows.mount(Static("[dim]Nenhum nó alocado ainda.[/dim]"))
        if not locked_rows.children:
            locked_rows.mount(Static("[dim]--[/dim]"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("talent_"):
            node_id = button_id.removeprefix("talent_")
            await self.app.client.allocate_talent(self._local_character_id(), node_id)
        elif button_id == "done":
            self.app.pop_screen()
