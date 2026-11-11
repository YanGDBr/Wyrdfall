from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.attributes import _RATES, ATTRIBUTE_NAMES, Atributo
from wyrdfall.domain.models import Stat
from wyrdfall.ui.screens.equipment import stat_rows
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, KeyValue, Panel, TitleBar

_STAT_LABELS = {
    Stat.PHYSICAL_DAMAGE_PERCENT: "dano físico",
    Stat.MAX_HP: "PV máx.",
    Stat.ARMOR_PENETRATION_PERCENT: "penetração",
    Stat.CRIT_CHANCE: "crítico",
    Stat.DODGE_CHANCE: "esquiva",
    Stat.SPEED: "velocidade",
    Stat.STATUS_RESIST: "resist. a status",
    Stat.DEFENSE: "defesa",
    Stat.ELEMENTAL_DAMAGE_PERCENT: "dano elemental",
    Stat.MAX_RESOURCE: "recurso máx.",
    Stat.GENERAL_ELEMENTAL_RESIST: "resist. elemental",
    Stat.RESOURCE_REGEN_PER_TURN: "regen. de recurso",
    Stat.HEALING_DONE_PERCENT: "cura causada",
    Stat.CRIT_RESIST: "resist. a crítico",
    Stat.CRIT_MULT: "dano crítico",
    Stat.PROC_CHANCE_PERCENT: "chance de proc",
}


_PERCENT_STATS = {
    Stat.PHYSICAL_DAMAGE_PERCENT, Stat.ARMOR_PENETRATION_PERCENT, Stat.CRIT_CHANCE, Stat.DODGE_CHANCE,
    Stat.STATUS_RESIST, Stat.ELEMENTAL_DAMAGE_PERCENT, Stat.GENERAL_ELEMENTAL_RESIST, Stat.HEALING_DONE_PERCENT,
    Stat.CRIT_RESIST, Stat.PROC_CHANCE_PERCENT,
}


def _scaling_text(attribute: Atributo) -> str:
    parts = []
    for attr, stat, rate in _RATES:
        if attr != attribute:
            continue
        label = _STAT_LABELS.get(stat, stat.value)
        if stat in _PERCENT_STATS:
            value = f"+{rate:.1%}"
        elif stat is Stat.CRIT_MULT:
            value = f"+{rate:.3f}×"
        else:
            value = f"+{rate:g}"
        parts.append(f"{value} {label}")
    return "\n".join(f"[dim]{p}[/dim]" for p in parts)


class AttributeScreen(Screen):
    """Always pushed on top of the DungeonScreen -- 'Concluído' just pops back.
    One box per attribute: what it scales, how much is invested, and the
    +1 button; the computed stats on the side update as points go in."""

    CSS = """
    AttributeScreen #side { width: 32; height: 100%; }
    AttributeScreen #side Panel { height: auto; }
    AttributeScreen #main { width: 1fr; height: 100%; }
    AttributeScreen #attribute-rows { height: auto; }
    AttributeScreen .attr { height: auto; }
    AttributeScreen .attr Panel { height: 11; }
    AttributeScreen .attr Button { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("", id="attribute-header")
            with Columns(classes="body fill"):
                with Vertical(id="side"):
                    with Panel("Pontos", variant="accent"):
                        yield Static("", id="attribute-points", classes="big")
                        yield Hint("Cada ponto reforça um atributo permanentemente nesta run (por ponto, abaixo).")
                    with Panel("Atributos de combate"):
                        yield KeyValue(id="stats")
                with Vertical(id="main"):
                    attributes = list(Atributo)
                    with Vertical(id="attribute-rows"):
                        with Columns(classes="attr"):
                            for attribute in attributes[:3]:
                                yield self._attribute_panel(attribute)
                        with Columns(classes="attr"):
                            for attribute in attributes[3:]:
                                yield self._attribute_panel(attribute)
            with ButtonRow(classes="actions"):
                yield Button("Concluído", id="done", variant="primary")
        yield Footer()

    def _attribute_panel(self, attribute: Atributo) -> Panel:
        return Panel(
            ATTRIBUTE_NAMES[attribute],
            Static("", id=f"invested_{attribute.value}", classes="big"),
            Static(_scaling_text(attribute)),
            Button(f"+1 {ATTRIBUTE_NAMES[attribute]}", id=f"attr_{attribute.value}", disabled=True),
        )

    def on_mount(self) -> None:
        self.app.client.on_update(self.refresh_attributes)
        self.call_after_refresh(self.refresh_attributes)

    def on_unmount(self) -> None:
        self.app.client.off_update(self.refresh_attributes)

    def on_screen_resume(self) -> None:
        self.refresh_attributes()

    def _local_character_id(self) -> str:
        return next(iter(self.app.client.local_character_ids()))

    def refresh_attributes(self) -> None:
        if not self.query("#stats"):
            return
        client = self.app.client
        hero = next(c for c in client.get_run().party if c.id == self._local_character_id())
        points = hero.attribute_points_available
        self.query_one("#attribute-header", TitleBar).update(f"Atributos -- {hero.name}")
        color = "green" if points else "dim"
        self.query_one("#attribute-points", Static).update(f"[bold {color}]{points}[/bold {color}] ponto{'s' if points != 1 else ''} para gastar")
        self.query_one("#stats", KeyValue).set_rows(stat_rows(hero, client.ruleset))
        for attribute in Atributo:
            invested = hero.attribute_points.get(attribute, 0)
            self.query_one(f"#invested_{attribute.value}", Static).update(f"[bold]{invested}[/bold] ponto{'s' if invested != 1 else ''}")
            button = self.query_one(f"#attr_{attribute.value}", Button)
            button.disabled = points <= 0
            button.variant = "success" if points > 0 else "default"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("attr_"):
            attribute = Atributo(button_id.removeprefix("attr_"))
            await self.app.client.allocate_attribute(self._local_character_id(), attribute)
        elif button_id == "done":
            self.app.pop_screen()
