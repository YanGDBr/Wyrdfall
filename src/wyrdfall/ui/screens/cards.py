from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.cards import CARD_DEFS
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, Panel, TitleBar

_RARITY_VARIANT = {"comum": "", "raro": "accent", "lendario": "warning"}


class CardsScreen(Screen):
    """Cartas (docs/design/10-sistemas-de-build.md §3.7): this client's own
    character's pending 1-of-3 offer as three side-by-side cards, and the
    cards it already holds below. Offers are per character, so a
    teammate's choice never touches yours; the screen refreshes off every
    broadcast like the others."""

    CSS = """
    CardsScreen #card-offer-rows { height: auto; }
    CardsScreen #card-offer-rows Panel { height: 12; }
    CardsScreen #card-offer-rows Button { margin-top: 1; }
    CardsScreen #held-panel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Cartas")
            yield Hint("", id="cards-status")
            yield Columns(id="card-offer-rows")
            with ButtonRow(id="offer-actions"):
                yield Button("Recusar a oferta", id="skip", disabled=True)
            with Panel("Cartas em posse", id="held-panel"):
                yield Static("", id="cards-held")
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.app.client.on_update(self.refresh_cards)
        self.call_after_refresh(self.refresh_cards)

    def on_unmount(self) -> None:
        self.app.client.off_update(self.refresh_cards)

    def _local_character(self):
        client = self.app.client
        local_id = next(iter(client.local_character_ids()), None)
        return next((c for c in client.get_run().party if c.id == local_id), None)

    def refresh_cards(self) -> None:
        if not self.query("#cards-status"):
            return
        character = self._local_character()
        if character is None:
            return
        offer = list(character.card_offer)
        status = (
            f"{character.name}: escolha 1 das {len(offer)} Cartas oferecidas -- a escolha é definitiva."
            if offer else f"{character.name}: nenhuma oferta pendente. Vencer um combate traz uma nova."
        )
        self.query_one("#cards-status", Hint).update(status)
        self.query_one("#skip", Button).disabled = not offer
        held = [
            f"[bold]{escape(CARD_DEFS[cid].name)}[/bold] [dim]({CARD_DEFS[cid].rarity.value}) -- {escape(CARD_DEFS[cid].description)}[/dim]"
            for cid in character.cards if cid in CARD_DEFS
        ]
        self.query_one("#cards-held", Static).update("\n".join(held) if held else "[dim]nenhuma ainda[/dim]")
        self.run_worker(self._render_offer(offer), exclusive=True, group="card-offer-rows")

    async def _render_offer(self, offer: list[str]) -> None:
        container = self.query_one("#card-offer-rows", Columns)
        await container.remove_children()
        for card_id in offer:
            card = CARD_DEFS[card_id]
            kind = "ativa" if card.is_active else "passiva"
            panel = Panel(
                f"{card.rarity.value} · {kind}",
                Static(f"[bold]{escape(card.name)}[/bold]\n"),
                Static(escape(card.description)),
                Button("Escolher", id=f"card_{card_id}", variant="primary"),
                variant=_RARITY_VARIANT.get(card.rarity.value, ""),
            )
            container.mount(panel)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        character = self._local_character()
        if button_id == "back":
            self.app.pop_screen()
        elif character is None:
            return
        elif button_id == "skip":
            await self.app.client.skip_card(character.id)
        elif button_id.startswith("card_"):
            await self.app.client.choose_card(character.id, button_id.removeprefix("card_"))
