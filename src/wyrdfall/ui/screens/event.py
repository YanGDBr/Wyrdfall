from functools import partial

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.content import EVENT_DEFS
from wyrdfall.domain.events import event_for_node
from wyrdfall.ui.connection_status import ConnectionStatusPanel
from wyrdfall.ui.widgets import ButtonRow, Columns, Panel, TitleBar, labeled_bar
from wyrdfall.ui.party_ready import PartyReadyPanel


def _option_hints(option) -> str:
    """The parts of an option a player can know up front (the outcome text
    itself stays a surprise): cost, danger, obvious gains."""
    hints = []
    if option.currency_delta < 0:
        hints.append(f"[yellow]custa {-option.currency_delta} Fragmentos[/yellow]")
    elif option.currency_delta > 0:
        hints.append(f"[green]+{option.currency_delta} Fragmentos[/green]")
    if option.damage_fraction > 0:
        hints.append(f"[red]dói ({option.damage_fraction:.0%} PV)[/red]")
    if option.heal_fraction > 0:
        hints.append(f"[green]cura {option.heal_fraction:.0%} PV[/green]")
    if option.talent_points:
        hints.append(f"[green]+{option.talent_points} talento[/green]")
    if option.wyrd_risk > 0:
        hints.append("[magenta]risco (Wyrd)[/magenta]")
    if option.blessing:
        hints.append("[cyan]bênção[/cyan]")
    return "  ".join(hints) if hints else "[dim]sem custo[/dim]"


class EventScreen(Screen):
    """Evento (docs/design/14-estrutura-da-run.md §5): pushed by
    DungeonScreen in place of a combat when the current node is an event.
    The event shown is computed here from the run seed + node index,
    exactly as GameSession does, so a joiner sees the same one the host
    resolves. The host chooses; the others follow the shared state and
    close this screen when the room is resolved."""

    CSS = """
    EventScreen #columns { height: auto; }
    EventScreen #columns Panel { height: auto; }
    EventScreen #event-options { height: auto; }
    EventScreen #event-options Panel { height: 9; }
    EventScreen #event-options Button { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield ConnectionStatusPanel()
            yield TitleBar("", id="event-title")
            with Columns(id="columns"):
                with Panel("O que acontece", variant="accent"):
                    yield Static("", id="event-text")
                with Panel("Grupo", variant="success"):
                    yield Static("", id="event-party")
            yield Columns(id="event-options")
            yield PartyReadyPanel()
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._encounter_index = self.app.client.get_run().encounter_index
        self._subscribed_client = self.app.client
        self._subscribed_client.on_update(self._queue_update)
        self.call_after_refresh(self.refresh_event)

    def on_unmount(self) -> None:
        self._subscribed_client.off_update(self._queue_update)

    def _queue_update(self) -> None:
        self.call_later(self.refresh_event)

    def refresh_event(self) -> None:
        if self.app.client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        if not self.query("#event-text"):
            return
        client = self.app.client
        run = client.get_run()
        if run.encounter_index != self._encounter_index:
            if self.app.screen is self and self.app.client.get_run().encounter_index != self._encounter_index:
                self.app.pop_screen()
            return
        event = event_for_node(run, EVENT_DEFS)
        self.query_one("#event-title", TitleBar).update(f"Evento -- {event.name}")
        self.query_one("#event-text", Static).update(escape(event.text))
        if not client.can_decide_for_party:
            self.query_one("#event-text", Static).update(escape(event.text) + "\n\n[dim]O host escolhe pelo grupo.[/dim]")
        blocks = []
        for character in run.party:
            computed = character.computed_stats(client.ruleset)
            blocks.append(
                f"[bold]{escape(character.name)}[/bold]  [dim]alinhamento {character.alignment_score:+.0f}[/dim]\n"
                + labeled_bar("PV", character.current_hp, computed.max_hp, width=14)
            )
        blocks.append(f"[dim]Fragmentos: {run.currency_earned}[/dim]")
        self.query_one("#event-party", Static).update("\n".join(blocks))
        self.run_worker(partial(self._render_options, event, run.currency_earned), exclusive=True, group="event-options")

    async def _render_options(self, event, currency: int) -> None:
        container = self.query_one("#event-options", Columns)
        await container.remove_children()
        for index, option in enumerate(event.options):
            unaffordable = (option.currency_delta < 0 and currency < -option.currency_delta) or not self.app.client.can_decide_for_party
            container.mount(Panel(
                f"opção {index + 1}",
                Static(f"[bold]{escape(option.label)}[/bold]\n"),
                Static(_option_hints(option)),
                Button("Escolher", id=f"option_{option.id}", disabled=unaffordable, variant="primary"),
            ))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
        elif button_id.startswith("option_"):
            await self.app.client.resolve_event(button_id.removeprefix("option_"))
            if self.app.screen is self and self.app.client.get_run().encounter_index != self._encounter_index:
                self.app.pop_screen()
