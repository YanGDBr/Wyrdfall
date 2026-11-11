from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.engine.session import REST_HEAL_FRACTION
from wyrdfall.ui.connection_status import ConnectionStatusPanel
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, Panel, TitleBar, labeled_bar
from wyrdfall.ui.party_ready import PartyReadyPanel


class RestScreen(Screen):
    """Sala de Descanso (docs/design/14-estrutura-da-run.md §5): pushed by
    DungeonScreen in place of a combat when the current node is a rest.
    Acampar heals the whole party, Meditar grants everyone a Ponto de
    Talento instead. The host chooses for the party; all clients follow
    the shared state and close the screen when the room is resolved."""

    CSS = """
    RestScreen #columns { height: auto; }
    RestScreen #columns Panel { height: auto; }
    RestScreen #choices Panel { height: 10; }
    RestScreen #choices Button { margin-top: 1; }
    RestScreen #choices { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield ConnectionStatusPanel()
            yield TitleBar("Sala de Descanso")
            if not self.app.client.can_decide_for_party:
                yield Hint("O host escolhe o descanso do grupo.")
            with Columns(id="columns"):
                with Panel("O lugar"):
                    yield Static("", id="rest-body")
                with Panel("Grupo", variant="success"):
                    yield Static("", id="rest-party")
            with Columns(id="choices"):
                with Panel("Acampar", variant="accent"):
                    yield Static(f"Cura [bold]{REST_HEAL_FRACTION:.0%}[/bold] do PV máximo de todos (e do Companheiro).")
                    yield Button("Acampar", id="acampar", variant="primary")
                with Panel("Meditar", variant="accent"):
                    yield Static("Sem cura -- [bold]+1 Ponto de Talento[/bold] para todos. Cargas de habilidade recarregam nas duas escolhas.")
                    yield Button("Meditar", id="meditar")
            yield PartyReadyPanel()
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._encounter_index = self.app.client.get_run().encounter_index
        self._subscribed_client = self.app.client
        self._subscribed_client.on_update(self._queue_update)
        self.call_after_refresh(self.refresh_rest)

    def on_unmount(self) -> None:
        self._subscribed_client.off_update(self._queue_update)

    def _queue_update(self) -> None:
        self.call_later(self.refresh_rest)

    def refresh_rest(self) -> None:
        if self.app.client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        if not self.query("#rest-body"):
            return
        client = self.app.client
        run = client.get_run()
        for choice in ("acampar", "meditar"):
            self.query_one(f"#{choice}", Button).disabled = not client.can_decide_for_party
        if run.encounter_index != self._encounter_index:
            # someone (a teammate, or this client a moment ago) already
            # resolved this rest -- follow the shared state
            if self.app.screen is self and self.app.client.get_run().encounter_index != self._encounter_index:
                self.app.pop_screen()
            return
        encounter = client.current_encounter()
        self.query_one("#rest-body", Static).update(escape(encounter.flavor_text))
        blocks = []
        for character in run.party:
            computed = character.computed_stats(client.ruleset)
            blocks.append(
                f"[bold]{escape(character.name)}[/bold]  [dim]talentos: {character.build.talent_tree.points_available}[/dim]\n"
                + labeled_bar("PV", character.current_hp, computed.max_hp, width=14)
            )
        self.query_one("#rest-party", Static).update("\n".join(blocks))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id in ("acampar", "meditar"):
            await self.app.client.resolve_rest(event.button.id)
            # a LocalGameClient notifies synchronously inside resolve_rest,
            # so refresh_rest may already have popped this screen
            if self.app.screen is self and self.app.client.get_run().encounter_index != self._encounter_index:
                self.app.pop_screen()
