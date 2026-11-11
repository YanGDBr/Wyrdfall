from wyrdfall.ui.party_ready import PartyReadyPanel
from functools import partial
from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.cards import CARD_DEFS, CARD_PRICES_BY_RARITY
from wyrdfall.domain.consumables import CONSUMABLE_SLOTS
from wyrdfall.domain.content import CONSUMABLE_DEFS
from wyrdfall.domain.shop import CONSUMABLE_PRICES, SHOP_REROLL_COST
from wyrdfall.engine.session import SessionError
from wyrdfall.ui.connection_status import ConnectionStatusPanel
from wyrdfall.ui.widgets import ButtonRow, Columns, KeyValue, Panel, TitleBar


class ShopScreen(Screen):
    """Vendedor (docs/design/14-estrutura-da-run.md §5): pushed by
    DungeonScreen when the current Sala Especial resolved to a shop.
    Stock is computed from the broadcast RunState, so every client sees
    the same shelf; buying/rerolling goes through the client like every
    other action, and "Seguir viagem" is what consumes the node."""

    CSS = """
    ShopScreen #columns { height: auto; }
    ShopScreen #columns Panel { height: auto; }
    ShopScreen #wallet { width: 34; }
    ShopScreen #shelf { height: auto; }
    ShopScreen #shelf Panel { height: auto; }
    ShopScreen #shelf Button { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield ConnectionStatusPanel()
            yield TitleBar("Vendedor")
            with VerticalScroll(classes="body-scroll"):
                with Columns(id="columns"):
                    with Panel("Sua bolsa", id="wallet", variant="accent"):
                        yield KeyValue(id="shop-status")
                        yield Button(f"Rerolar ({SHOP_REROLL_COST} Frag.)", id="reroll")
                    with Panel("O vendedor"):
                        yield Static("", id="shop-body")
                yield Columns(id="shelf")
            yield PartyReadyPanel()
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
                yield Button("Seguir viagem" if self.app.client.can_decide_for_party else "Aguardando o host", id="leave", variant="primary", disabled=not self.app.client.can_decide_for_party)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#leave", Button).display = self.app.client.get_readiness() is None
        self._encounter_index = self.app.client.get_run().encounter_index
        self._subscribed_client = self.app.client
        self._subscribed_client.on_update(self._queue_update)
        self.call_after_refresh(self.refresh_shop)

    def on_unmount(self) -> None:
        self._subscribed_client.off_update(self._queue_update)

    def _queue_update(self) -> None:
        self.call_later(self.refresh_shop)

    def _stock_generation(self) -> str:
        run = self._subscribed_client.get_run()
        rerolls = run.shop.rerolls if run.shop is not None and run.shop.node_index == run.encounter_index else 0
        return f"{run.encounter_index}:{rerolls}"

    def refresh_shop(self) -> None:
        if self.app.client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        if not self.query("#shop-body"):
            return
        client = self.app.client
        self.query_one("#leave", Button).display = client.get_readiness() is None
        run = client.get_run()
        if run.encounter_index != self._encounter_index:
            if self.app.screen is self:
                self.app.pop_screen()
            return
        self.query_one("#shop-body", Static).update(escape(client.current_encounter().flavor_text))
        self.query_one("#shop-status", KeyValue).set_rows([
            ("Fragmentos", f"[bold]{run.currency_earned}[/bold]"),
            ("Bolsa", f"{len(run.consumables)}/{CONSUMABLE_SLOTS}"),
        ])
        self.query_one("#reroll", Button).disabled = run.currency_earned < SHOP_REROLL_COST
        self.run_worker(
            partial(self._render_rows,
                client.shop_stock(), client.shop_sold_slots(), run.currency_earned, len(run.consumables),
                client.shop_card(), client.shop_card_sold(),
                self._stock_generation(),
            ),
            exclusive=True, group="shop-rows",
        )

    async def _render_rows(
        self, stock: list[str], sold: list[int], currency: int, pouch_size: int, card_id: str, card_sold: bool,
        generation: str,
    ) -> None:
        shelf = self.query_one("#shelf", Columns)
        await shelf.remove_children()
        for slot, consumable_id in enumerate(stock):
            consumable = CONSUMABLE_DEFS[consumable_id]
            price = CONSUMABLE_PRICES[consumable_id]
            if slot in sold:
                shelf.mount(Panel("vendido", Static(f"[dim]{escape(consumable.name)}[/dim]")))
                continue
            disabled = currency < price or pouch_size >= CONSUMABLE_SLOTS
            shelf.mount(Panel(
                f"{price} Fragmentos",
                Static(f"[bold]{escape(consumable.name)}[/bold]\n"),
                Static(f"[dim]{escape(consumable.description)}[/dim]"),
                Button("Comprar", id=f"buy_{slot}", name=generation, disabled=disabled, variant="primary"),
            ))
        card = CARD_DEFS[card_id]
        card_price = CARD_PRICES_BY_RARITY[card.rarity]
        if card_sold:
            shelf.mount(Panel("vendida", Static(f"[dim]Carta {escape(card.name)}[/dim]")))
        else:
            shelf.mount(Panel(
                f"Carta · {card_price} Frag.",
                Static(f"[bold]{escape(card.name)}[/bold]\n"),
                Static(f"[dim]{escape(card.description)}[/dim]"),
                Button("Comprar carta", id="buy_card", name=f"{generation}:{card_id}",
                       disabled=currency < card_price, variant="primary"),
                variant="accent",
            ))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
            return
        client = self._subscribed_client
        if self.app.client is not client or client.get_run().encounter_index != self._encounter_index:
            return
        try:
            if button_id == "reroll":
                await client.reroll_shop()
            elif button_id == "leave":
                await client.leave_node()
                if self.app.screen is self and client.get_run().encounter_index != self._encounter_index:
                    self.app.pop_screen()
            elif button_id == "buy_card":
                if event.button.name != f"{self._stock_generation()}:{client.shop_card()}":
                    raise SessionError("A oferta mudou. Confira a nova carta antes de comprar.")
                local_id = next(iter(client.local_character_ids()), None)
                if local_id is not None:
                    await client.buy_card(local_id)
            elif button_id.startswith("buy_"):
                if event.button.name != self._stock_generation():
                    raise SessionError("O estoque mudou. Confira a nova oferta antes de comprar.")
                await client.buy_consumable(int(button_id.removeprefix("buy_")))
        except SessionError as exc:
            self.notify(str(exc), severity="warning")
            if self.app.screen is self:
                self.refresh_shop()
