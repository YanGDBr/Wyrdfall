"""Teclas remapeáveis (docs/design/09-roadmap.md decision 7, Fase 2's
"remapear teclas nas opções"): the small set of keyboard actions the
game has, each bound to one Textual key name, persisted in
MetaProgressionState.keybindings. Screens ask `action_for(bindings,
key)` instead of hardcoding "1".."9"/"space"."""

from __future__ import annotations

# action id -> default key (Textual key names)
DEFAULT_KEYBINDINGS: dict[str, str] = {
    **{f"action_{n}": str(n) for n in range(1, 10)},  # the Nth action-bar button
    "minigame": "space",  # Parry / Janela de Tempo / Canalização
}

ACTION_LABELS: dict[str, str] = {
    **{f"action_{n}": f"Ação {n} da barra" for n in range(1, 10)},
    "minigame": "Minigame (aparar / janela / canalizar)",
}


def effective_bindings(overrides: dict[str, str] | None) -> dict[str, str]:
    bindings = dict(DEFAULT_KEYBINDINGS)
    for action, key in (overrides or {}).items():
        if action in bindings:
            bindings[action] = key  # "" = deliberately unbound
    return bindings


def action_for(bindings: dict[str, str], key: str) -> str | None:
    for action, bound in bindings.items():
        if bound and bound == key:
            return action
    return None


def rebind(overrides: dict[str, str], action: str, key: str) -> dict[str, str]:
    """Returns a new overrides dict with `action` on `key`; any other action
    that held `key` is moved back to its default so two actions never share
    a key."""
    if action not in DEFAULT_KEYBINDINGS or not key:
        return dict(overrides)
    new = dict(overrides)
    for other, bound in effective_bindings(new).items():
        if other != action and bound == key:
            new.pop(other, None)
            if DEFAULT_KEYBINDINGS[other] == key:
                new[other] = ""  # default collides too: leave the other unbound
    new[action] = key
    return new
