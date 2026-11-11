"""The UI kit every screen is built from: titled boxes, bars, key/value
grids, tab bars and button rows. One vocabulary, so screens look and
behave alike -- a Panel is always a rounded box with its name on the
border, a stat is always `label  value`, a bar is always `label ████░░ n/m`.
"""

from __future__ import annotations

from typing import Iterable

from rich.markup import escape
from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, ContentSwitcher, Static

# Loaded by the App (app-level CSS beats widget DEFAULT_CSS, so the kit's
# layout rules must live at that priority to win over `Button { width }`).
KIT_CSS = """
    Panel {
        border: round $secondary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        height: auto;
        width: 1fr;
    }
    Panel.accent { border: round $accent; border-title-color: $accent; }
    Panel.success { border: round $success; border-title-color: $success; }
    Panel.danger { border: round $error; border-title-color: $error; }
    Panel.warning { border: round $warning; border-title-color: $warning; }
    Panel.fill { height: 1fr; }
    Panel > Static { width: 100%; }
    
    ButtonRow { height: auto; width: 100%; }
    ButtonRow > Button { width: 1fr; margin: 0 1 0 0; }
    ButtonRow > Button:last-child { margin: 0; }
    
    Columns { height: auto; width: 100%; }
    Columns > * { width: 1fr; }
    Columns.fill { height: 1fr; }
    Columns.fill > * { height: 100%; }
    
    Rows { height: auto; width: 100%; }
    Rows > Button { height: 1; min-height: 1; border: none; margin: 0; width: 100%; content-align-horizontal: left; text-align: left; }
    Rows > Static { width: 100%; }
    
    Hint { color: $text-muted; width: 100%; }
    
    TitleBar {
        width: 100%;
        height: 1;
        background: $accent 20%;
        color: $accent;
        text-style: bold;
        padding: 0 1;
    }
    
    Tabbed { height: 1fr; width: 100%; }
    Tabbed > ButtonRow { height: 3; }
    Tabbed > ButtonRow > Button { width: 1fr; min-width: 0; padding: 0; }
    Tabbed > ContentSwitcher { height: 1fr; width: 100%; }
    Tabbed > ContentSwitcher > * { height: 100%; width: 100%; }
    
"""


class Panel(Vertical):
    """A titled, bordered box. `variant` picks the border colour: "" (neutral),
    "accent", "success", "danger", "warning"."""

    def __init__(self, title: str = "", *children: Widget, variant: str = "", id: str | None = None,
                 classes: str | None = None) -> None:
        all_classes = " ".join(c for c in (variant, classes or "") if c) or None
        super().__init__(*children, id=id, classes=all_classes)
        if title:
            self.border_title = title


class ButtonRow(Horizontal):
    """Buttons side by side, equal width, one row high."""


class Columns(Horizontal):
    """Side-by-side panels; each child takes an equal share unless it sets
    its own width."""


class Rows(Vertical):
    """A vertical list that sizes to its content (never steals height from
    its siblings)."""


class Hint(Static):
    """Muted helper text."""


class TitleBar(Static):
    """The one-line screen title strip at the top of every screen."""


def bar(current: float, maximum: float, width: int = 16, color: str = "green") -> str:
    """`████████░░░░` in Rich markup."""
    maximum = max(1.0, maximum)
    fraction = max(0.0, min(1.0, current / maximum))
    filled = max(0, min(width, round(width * fraction)))
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (width - filled)}[/dim]"


def hp_color(fraction: float) -> str:
    if fraction <= 0.3:
        return "red"
    if fraction <= 0.6:
        return "yellow"
    return "green"


def labeled_bar(label: str, current: float, maximum: float, width: int = 16, color: str | None = None) -> str:
    """`PV   ████░░  41/50` -- the colour follows the fraction unless given."""
    fraction = current / max(1.0, maximum)
    color = color or hp_color(fraction)
    return f"{escape(label):<8}{bar(current, maximum, width, color)} {current:.0f}/{maximum:.0f}"


def kv(rows: Iterable[tuple[str, object]], key_style: str = "dim") -> Table:
    """A two-column label/value grid for a Static."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=key_style, no_wrap=True)
    table.add_column()
    for key, value in rows:
        table.add_row(escape(str(key)), str(value))
    return table


class KeyValue(Static):
    """A Static that renders `kv(rows)`; `.text` is the plain "key: value"
    form (what tests and logs read)."""

    text: str = ""

    def set_rows(self, rows: Iterable[tuple[str, object]]) -> None:
        rows = list(rows)
        self.text = "\n".join(f"{key}: {value}" for key, value in rows)
        self.update(kv(rows))


class Tabbed(Vertical):
    """A tab bar (`#tab_<key>` buttons) over a ContentSwitcher of panes
    (`#pane_<key>`). Screens add panes with `add_pane` inside compose and
    switch with `show(key)`; the active tab's button is highlighted."""

    def __init__(self, tabs: list[tuple[str, str]], initial: str, id: str | None = None) -> None:
        super().__init__(id=id)
        self._tabs = tabs
        self._initial = initial
        self._panes: dict[str, Widget] = {}

    def add_pane(self, key: str, pane: Widget) -> Widget:
        pane.id = f"pane_{key}"
        self._panes[key] = pane
        return pane

    def compose(self) -> ComposeResult:
        with ButtonRow(id="tabbar"):
            for key, label in self._tabs:
                yield Button(label, id=f"tab_{key}", variant="primary" if key == self._initial else "default")
        with ContentSwitcher(initial=f"pane_{self._initial}", id="tab-switcher"):
            for key, _label in self._tabs:
                pane = self._panes.get(key)
                if pane is not None:
                    yield pane

    @property
    def active(self) -> str:
        current = self.query_one("#tab-switcher", ContentSwitcher).current or ""
        return current.removeprefix("pane_")

    def show(self, key: str) -> None:
        if key not in self._panes:
            return
        self.query_one("#tab-switcher", ContentSwitcher).current = f"pane_{key}"
        for tab_key, _ in self._tabs:
            button = self.query_one(f"#tab_{tab_key}", Button)
            button.variant = "primary" if tab_key == key else "default"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("tab_") and button_id.removeprefix("tab_") in self._panes:
            event.stop()
            self.show(button_id.removeprefix("tab_"))


def status_chips(ruleset, statuses) -> str:
    chips = []
    for s in statuses:
        name = ruleset.statuses[s.status_id].name if s.status_id in ruleset.statuses else s.status_id
        suffix = f"×{s.stacks}" if s.stacks > 1 else ""
        chips.append(f"[magenta]{escape(name)}{suffix}[/magenta]")
    return "  ".join(chips)
