from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.contracts import CONTRACT_DEFS
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, Panel, Rows, TitleBar


class ContractsScreen(Screen):
    """Contratos de Run (docs/design/08-itens-crafting.md): the run's offer
    (accept any, decline the rest) as cards, plus what's accepted and
    completed. Follows the shared state like every other node screen."""

    CSS = """
    ContractsScreen #contract-offer { height: auto; }
    ContractsScreen #contract-offer Panel { height: 11; }
    ContractsScreen #contract-offer Button { margin-top: 1; }
    ContractsScreen #accepted-panel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Contratos de Run")
            yield Hint("Objetivos opcionais. Cada um paga Fragmentos na hora e Ecos no fim da run, uma vez só.")
            if not self.app.client.can_decide_for_party:
                yield Hint("O host aceita ou recusa os contratos do grupo.")
            yield Columns(id="contract-offer")
            with ButtonRow(id="contract-actions"):
                yield Button("Recusar o resto", id="decline_rest", disabled=True)
            with Panel("Aceitos", id="accepted-panel"):
                yield Rows(id="contract-rows")
            with ButtonRow(classes="actions"):
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.app.client.on_update(self.refresh_contracts)
        self.call_after_refresh(self.refresh_contracts)

    def on_unmount(self) -> None:
        self.app.client.off_update(self.refresh_contracts)

    def refresh_contracts(self) -> None:
        if not self.query("#contract-rows"):
            return
        self.run_worker(self._render_rows(), exclusive=True, group="contract-rows")

    async def _render_rows(self) -> None:
        run = self.app.client.get_run()
        offer = self.query_one("#contract-offer", Columns)
        await offer.remove_children()
        for contract_id in run.contract_offer:
            contract = CONTRACT_DEFS[contract_id]
            offer.mount(Panel(
                "em oferta",
                Static(f"[bold]{escape(contract.name)}[/bold]\n"),
                Static(escape(contract.description)),
                Static(f"\n[green]+{contract.reward_fragments} Fragmentos[/green] · [cyan]+{contract.reward_ecos} Ecos[/cyan]"),
                Button("Aceitar", id=f"accept_{contract_id}", variant="primary", disabled=not self.app.client.can_decide_for_party),
                variant="accent",
            ))
        self.query_one("#decline_rest", Button).disabled = not run.contract_offer or not self.app.client.can_decide_for_party

        container = self.query_one("#contract-rows", Rows)
        await container.remove_children()
        for contract_id in run.accepted_contracts:
            contract = CONTRACT_DEFS[contract_id]
            done = contract_id in run.completed_contracts
            mark = "[green]✓[/green]" if done else "[dim]○[/dim]"
            container.mount(Static(f"{mark} [bold]{escape(contract.name)}[/bold] [dim]-- {escape(contract.description)}[/dim]"
                                   + (" [green]concluído![/green]" if done else "")))
        if not run.accepted_contracts:
            container.mount(Static("[dim]Nenhum contrato aceito nesta run.[/dim]"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
        elif button_id.startswith("accept_"):
            await self.app.client.accept_contract(button_id.removeprefix("accept_"))
        elif button_id == "decline_rest":
            await self.app.client.decline_contracts()
