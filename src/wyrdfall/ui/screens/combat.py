from __future__ import annotations

import re
from functools import partial

from rich.markup import escape
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, RichLog, Static

from wyrdfall.domain.combat import ParryResult
from wyrdfall.domain.abilities import ROLE_ORDER, Ability, infer_role
from wyrdfall.domain.character import RESOURCE_NAMES
from wyrdfall.domain.combat import Action
from wyrdfall.domain.content import CONSUMABLE_DEFS
from wyrdfall.domain.content.terrain import AREA_TERRAINS
from wyrdfall.domain.keybindings import action_for, effective_bindings
from wyrdfall.domain.slots import STANCE_NAMES, STANCES
from wyrdfall.ui.connection_status import ConnectionStatusPanel
from wyrdfall.ui.widgets import Columns, Panel, labeled_bar, status_chips
from wyrdfall.ui.party_ready import PartyReadyPanel


# Cosmetic keyword highlighting for the plain-text combat log the domain
# layer produces -- kept entirely in the UI so combat.py (domain) never has
# to know about Rich markup. Order matters: broader patterns (a full "sofre
# N de dano" line) go first so later, narrower patterns don't fight them for
# the same substring.
_LOG_HIGHLIGHTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sofre (\d+) de dano"), r"sofre [bold red]\1[/bold red] de dano"),
    (re.compile(r"\(Crítico!\)"), "[bold red]\\g<0>[/bold red]"),
    (re.compile(r"\(Bloqueado\)"), "[bold blue]\\g<0>[/bold blue]"),
    (re.compile(r"\(\d+ absorvido pelo escudo\)"), "[cyan]\\g<0>[/cyan]"),
    (re.compile(r"recupera (\d+) de (PV|Resolução)"), r"recupera [bold green]\1[/bold green] de \2"),
    (re.compile(r"ganha um escudo de \d+"), "[bold cyan]\\g<0>[/bold cyan]"),
    (re.compile(r"esquiva do ataque!"), "[italic cyan]\\g<0>[/italic cyan]"),
    (re.compile(r"apara o ataque de [^!]+!"), "[bold magenta]\\g<0>[/bold magenta]"),
    (re.compile(r"falha ao tentar aparar!"), "[dim]\\g<0>[/dim]"),
    (re.compile(r"foi derrotado!"), "[bold red]\\g<0>[/bold red]"),
    (re.compile(r"recusa cair -- Nunca Desista!"), "[bold yellow]\\g<0>[/bold yellow]"),
    (re.compile(r"resiste ao efeito: [^.]+\."), "[dim]\\g<0>[/dim]"),
]


def _colorize_log_line(line: str) -> str:
    highlighted = escape(line)
    for pattern, replacement in _LOG_HIGHLIGHTS:
        highlighted = pattern.sub(replacement, highlighted)
    return highlighted


_ROLE_VARIANTS = {
    "Dano": "primary",
    "Controle": "warning",
    "Debuff": "warning",
    "Buff": "success",
    "Cura": "success",
    "Utilidade": "default",
    "Invocação": "default",
}


class CombatScreen(Screen):
    CSS = """
    CombatScreen #turn-order { height: 3; width: 100%; }
    CombatScreen #combat-top { height: auto; max-height: 45%; }
    CombatScreen #action-panel { height: auto; max-height: 40%; }
    CombatScreen #combat-log { border: none; padding: 0; background: transparent; }
    CombatScreen #log-panel { height: 1fr; }
    CombatScreen #action-bar {
        layout: grid;
        grid-size: 4;
        grid-gutter: 1 1;
        height: auto;
        max-height: 16;
        width: 100%;
        border: none;
        padding: 0;
    }
    CombatScreen #action-bar Button { width: 100%; min-width: 0; margin: 0; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="combat-root"):
            yield ConnectionStatusPanel()
            with Panel("Ordem de turno", id="turn-order"):
                yield Static("", id="turn-order-body")
            with Columns(id="combat-top"):
                with Panel("Grupo", variant="success"):
                    yield Static("", id="party-panel")
                with Panel("Inimigos", variant="danger"):
                    yield Static("", id="enemy-panel")
            with Panel("Registro", id="log-panel", classes="fill"):
                yield RichLog(id="combat-log", wrap=True, markup=True)
            with Panel("Ações", variant="accent", id="action-panel"):
                yield PartyReadyPanel()
                yield VerticalScroll(id="action-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.app.discover_enemies_in_current_encounter()
        self.pending_ability: Ability | None = None
        self.mode: str = "select_ability"
        self._last_log_length = 0
        self._ai_timer_scheduled = False
        self._navigated = False
        self._parry_prompt_shown = False
        self._parry_modal = None
        self._parry_request_id = None
        self._answered_parry_id = None
        self._challenge_running = False
        self.query_one("#combat-log", RichLog).write("[bold]A batalha começa![/bold]")
        self._subscribed_client = self.app.client
        if self._subscribed_client is None:
            return
        self._subscribed_client.on_update(self._queue_update)
        self.handle_update()

    def on_unmount(self) -> None:
        if self._subscribed_client is not None:
            self._subscribed_client.off_update(self._queue_update)

    def _queue_update(self) -> None:
        self.call_later(self.handle_update)

    # -- rendering -----------------------------------------------------------

    def handle_update(self) -> None:
        client = self.app.client
        if client is None or getattr(self.app, "_leaving_run", False):
            return
        state = client.get_combat_state()
        pending = state.pending_parry if state else None
        if self._parry_modal is not None and self._parry_modal.is_mounted:
            if client.is_paused or pending is None or pending.request_id != self._parry_request_id:
                self._parry_modal._finish(ParryResult.DECLINED)
                return  # resume navigation after the modal worker finishes
        if state is None or client.get_last_summary() is not None:
            # The run advanced past this encounter -- either back to the
            # dungeon (state is None, no summary) or the run is over (a
            # summary appeared). Either way every client, whoever pressed
            # "Continue", reacts to the broadcast the same way.
            if not self._navigated:
                self._navigated = True
                self.run_worker(self._navigate_away, exclusive=True, group="combat-nav")
            return
        if len(state.log) > self._last_log_length:
            self.write_log(state.log[self._last_log_length :])
            self._last_log_length = len(state.log)
        self.refresh_panels()
        # Rebuilding the action bar removes and re-mounts buttons, which are
        # async operations in Textual. Updates can arrive faster than that
        # completes (e.g. finalize_run's own notify firing while a button
        # press is still being handled), so this is coalesced through an
        # exclusive worker rather than awaited inline -- a superseded render
        # is cancelled instead of racing a remove/mount against the next one.
        self.run_worker(self.render_actions, exclusive=True, group="combat-action-bar")

    def _combatant_card(self, c, ruleset, current_id: str | None, show_resource: bool) -> str:
        stats = c.computed_stats(ruleset)
        marker = "[bold yellow]➤[/bold yellow] " if c.id == current_id else "  "
        if not c.is_alive and not c.is_player:
            name = f"[dim strike]{escape(c.name)}[/dim strike] [dim](derrotado)[/dim]"
        else:
            name = f"[bold]{escape(c.name)}[/bold]" if c.id == current_id else escape(c.name)
        if c.is_incapacitated:
            name += " [bold red](incapacitado)[/bold red]"
        if c.is_companion:
            name += " [dim](companheiro)[/dim]"
        transform = ruleset.transforms.get(c.active_transform_id or "")
        if transform is not None:
            name += f" [bold magenta]{escape(transform.glyph)} {escape(transform.name)}[/bold magenta]"
        lines = [f"{marker}{name}", f"    {labeled_bar('PV', c.current_hp, stats.max_hp, width=14)}"]
        if show_resource and not c.is_companion:
            lines.append(
                f"    {labeled_bar(RESOURCE_NAMES[c.resource_kind][:7], c.current_resource, stats.max_resource, width=14, color='cyan')}"
            )
        if c.shield_hp > 0:
            lines.append(f"    [cyan]Escudo {c.shield_hp:.0f}[/cyan]")
        if stats.max_poise > 0 and not c.is_player:
            lines.append(f"    {labeled_bar('Postura', c.current_poise, stats.max_poise, width=14, color='yellow')}")
        if c.is_player and not c.is_companion:
            lines.append(f"    [dim]Postura de combate: {STANCE_NAMES[c.current_stance]}[/dim]")
        chips = status_chips(ruleset, c.statuses)
        if chips:
            lines.append(f"    {chips}")
        return "\n".join(lines)

    def refresh_panels(self) -> None:
        client = self.app.client
        state = client.get_combat_state()
        ruleset = client.ruleset
        current_id = state.current_actor_id() if not state.is_over else None

        order = []
        for cid in state.turn_order:
            c = state.combatants.get(cid)
            if c is None or not c.is_alive:
                continue
            label = escape(c.name)
            if cid == current_id:
                order.append(f"[bold reverse] {label} [/bold reverse]")
            else:
                color = "green" if c.is_player else "red"
                order.append(f"[{color}]{label}[/{color}]")
        self.query_one("#turn-order-body", Static).update("  →  ".join(order) + f"   [dim]rodada {state.round_number}[/dim]")

        party_cards = [
            self._combatant_card(state.combatants[cid], ruleset, current_id, show_resource=True) for cid in state.party_ids()
        ]
        self.query_one("#party-panel", Static).update("\n\n".join(party_cards))

        enemy_cards = [
            self._combatant_card(state.combatants[cid], ruleset, current_id, show_resource=False) for cid in state.enemy_ids()
        ]
        terrain = AREA_TERRAINS.get(state.terrain_id or "")
        terrain_line = f"[italic dim]Terreno: {escape(terrain.name)} -- {escape(terrain.description)}[/italic dim]\n\n" if terrain else ""
        self.query_one("#enemy-panel", Static).update(terrain_line + "\n\n".join(enemy_cards))

    def _set_action_title(self, title: str) -> None:
        self.query_one("#action-panel", Panel).border_title = title

    async def render_actions(self) -> None:
        client = self.app.client
        if client is None or client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        state = client.get_combat_state()
        if state is None or not self.is_mounted:
            return
        bar = self.query_one("#action-bar", VerticalScroll)
        await bar.remove_children()
        if self.app.client is not client or getattr(self.app, "_leaving_run", False) or client.get_combat_state() is not state:
            return

        if client.is_paused:
            bar.mount(Static(client.connection_status))
            return

        if state.is_over:
            variant = "success" if state.victory else "error"
            label = "Continuar" if state.victory else "Continuar (Derrota)"
            self._set_action_title("Vitória!" if state.victory else "Derrota")
            if client.get_readiness() is not None:
                return
            can_decide = client.can_decide_for_party
            bar.mount(Button(label if can_decide else "Aguardando o host", id="combat_continue", variant=variant, disabled=not can_decide))
            return

        if state.pending_parry is not None:
            await self._handle_pending_parry(state, bar)
            return

        actor_id = state.current_actor_id()
        actor = state.combatants[actor_id]

        if actor.acts_automatically:
            self._set_action_title(f"Vez de {actor.name}")
            bar.mount(Static(f"[italic dim]{escape(actor.name)} está agindo...[/italic dim]"))
            if not self._ai_timer_scheduled:
                self._ai_timer_scheduled = True
                self.set_timer(self.app.ai_turn_delay_seconds(), self._fire_ai_turn)
            return

        if actor_id not in client.local_character_ids():
            self._set_action_title(f"Vez de {actor.name}")
            bar.mount(Static(f"[italic dim]Aguardando {escape(actor.name)} agir...[/italic dim]"))
            return

        if self.mode == "select_target" and self.pending_ability is not None:
            self._set_action_title(f"{self.pending_ability.name} -- escolha o alvo")
            for target_id in client.legal_target_ids(actor_id, self.pending_ability):
                target = state.combatants[target_id]
                bar.mount(
                    Button(f"{target.name} ({target.current_hp:.0f} PV)", id=f"target_{target_id}", variant="warning")
                )
            bar.mount(Button("Cancelar", id="cancel_target"))
            return

        self.mode = "select_ability"
        self._set_action_title(f"Sua vez, {actor.name} -- escolha a ação (1-9)")
        # Papel (11-habilidades.md §4.4): the bar is grouped by role order
        # so damage comes first and utility last, whatever the pool order
        abilities = sorted(client.legal_abilities(actor_id), key=lambda a: ROLE_ORDER.index(infer_role(a)))
        for ability in abilities:
            badges = []
            if ability.resource_cost:
                badges.append(f"{ability.resource_cost:.0f}⟡")
            if ability.cooldown_turns:
                badges.append(f"↻{ability.cooldown_turns}")
            if ability.challenge is not None:
                badges.append("★")
            badge = f"  [dim]{' '.join(badges)}[/dim]" if badges else ""
            role = infer_role(ability)
            bar.mount(Button(f"{ability.name}{badge}", id=f"ability_{ability.id}", variant=_ROLE_VARIANTS.get(role, "default")))
        # Consumíveis em combate (14-estrutura-da-run.md §6): the shared pouch,
        # minus Tomos (out-of-combat only) -- one action, spends the turn
        potions = [
            (index, CONSUMABLE_DEFS[cid]) for index, cid in enumerate(client.get_run().consumables)
            if CONSUMABLE_DEFS[cid].teaches_ability is None
        ]
        for index, consumable in potions:
            bar.mount(Button(f"Beber {consumable.name}", id=f"consumable_{index}_{consumable.id}", variant="success"))
        # Posturas (docs/design/10-sistemas-de-build.md §3.9) come AFTER the
        # abilities so the digit shortcuts keep pointing at abilities first.
        for stance in STANCES:
            active = actor.current_stance == stance
            label = f"Postura {STANCE_NAMES[stance]}{' ✓' if active else ''}"
            bar.mount(Button(label, id=f"stance_{stance}", disabled=active or actor.stance_switched_this_turn))

    async def _handle_pending_parry(self, state, bar: VerticalScroll) -> None:
        client = self.app.client
        pending = state.pending_parry
        if pending.defender_id not in client.local_character_ids():
            defender_name = state.combatants[pending.defender_id].name
            self._set_action_title("Aparo pendente")
            bar.mount(Static(f"[italic dim]{escape(defender_name)} está decidindo se apara...[/italic dim]"))
            return

        if self._parry_prompt_shown or self._answered_parry_id == pending.request_id:
            return  # already awaiting the modal's result from a previous render
        self._parry_prompt_shown = True
        self._set_action_title("Aparar!")
        bar.mount(Static("[bold yellow]Prepare-se para aparar...[/bold yellow]"))

        # The modal must outlive action-bar renders. An exclusive render
        # worker can be cancelled by any incoming state broadcast.
        self.run_worker(partial(self._play_parry, pending, client), exclusive=False, group="combat-parry")

    async def _play_parry(self, pending, client) -> None:
        from wyrdfall.ui.screens.skill_challenge import SkillChallengeScreen
        self._parry_request_id = pending.request_id
        try:
            state = client.get_combat_state()
            if state is None or state.pending_parry is None or state.pending_parry.request_id != pending.request_id:
                return
            self._parry_modal = SkillChallengeScreen(state.combatants[pending.defender_id].name,
                                                     state.combatants[pending.attacker_id].name)
            result = await self.app.push_screen_wait(self._parry_modal)
            state = client.get_combat_state()
            if not client.is_paused and state is not None and state.pending_parry is not None and state.pending_parry.request_id == pending.request_id:
                self._answered_parry_id = pending.request_id
                await client.respond_to_parry(pending.defender_id, result)
        finally:
            self._parry_modal = None
            self._parry_request_id = None
            self._parry_prompt_shown = False
            if self.is_mounted and self.app.client is client:
                self.handle_update()

    async def _fire_ai_turn(self) -> None:
        self._ai_timer_scheduled = False
        client = self.app.client
        if client is self._subscribed_client:
            await client.resolve_ai_if_needed()

    # -- interaction -----------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        # Accessibility: "action_N" (digits 1-9 by default, remappable in
        # the Guild -- docs/design/09-roadmap.md decision 7) picks the Nth
        # currently visible action-bar button, same as clicking it.
        action = action_for(effective_bindings(self.app.meta.keybindings), event.key or "")
        if action and action.startswith("action_"):
            index = int(action.removeprefix("action_")) - 1
            buttons = list(self.query("#action-bar Button"))
            if 0 <= index < len(buttons) and not buttons[index].disabled:
                event.stop()
                button_id = buttons[index].id or ""
                self.run_worker(self._activate(button_id), exclusive=False)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        await self._activate(event.button.id or "")

    async def _activate(self, button_id: str) -> None:
        client = self.app.client
        if client is not self._subscribed_client or client.is_paused or self._challenge_running:
            return
        state = client.get_combat_state()
        if state is None:
            return

        if button_id == "combat_continue":
            if state.is_over and client.can_decide_for_party and client.get_readiness() is None:
                await self.finish_combat()
            return
        if state.is_over or state.pending_parry is not None or state.current_actor_id() not in client.local_character_ids():
            return
        if button_id.startswith("ability_"):
            ability_id = button_id.removeprefix("ability_")
            ability = client.ruleset.abilities[ability_id]
            if ability.requires_target:
                self.pending_ability = ability
                self.mode = "select_target"
                self.run_worker(self.render_actions, exclusive=True, group="combat-action-bar")
            else:
                await self.take_player_action(ability_id, [])
        elif button_id.startswith("target_"):
            ability = self.pending_ability
            if ability is None:
                return  # An earlier click or keypress already consumed this selection.
            target_id = button_id.removeprefix("target_")
            self.pending_ability = None
            self.mode = "select_ability"
            await self.take_player_action(ability.id, [target_id])
        elif button_id == "cancel_target":
            self.pending_ability = None
            self.mode = "select_ability"
            self.run_worker(self.render_actions, exclusive=True, group="combat-action-bar")
        elif button_id.startswith("consumable_"):
            consumable_id = button_id.split("_", 2)[2]
            try:
                await client.use_consumable(state.current_actor_id(), consumable_id)
            except Exception as exc:
                self.query_one("#combat-log", RichLog).write(f"[bold red]! {escape(str(exc))}[/bold red]")
        elif button_id.startswith("stance_"):
            try:
                await client.set_stance(state.current_actor_id(), button_id.removeprefix("stance_"))
            except Exception as exc:
                self.query_one("#combat-log", RichLog).write(f"[bold red]! {escape(str(exc))}[/bold red]")

    async def take_player_action(self, ability_id: str, target_ids: list[str]) -> None:
        client = self.app.client
        ability = client.ruleset.abilities[ability_id]
        # Minigame de Habilidade (docs/design/11-habilidades.md §9): played
        # on this client before the action is submitted; only the score
        # travels. push_screen_wait needs a worker, so the minigame branch
        # hops into one and re-enters here with the score in hand.
        if ability.challenge is not None:
            self._challenge_running = True
            self.run_worker(self._play_challenge_then_act(ability, target_ids), exclusive=False, group="combat-challenge")
            return
        await self._submit_action(ability_id, target_ids, None)

    async def _play_challenge_then_act(self, ability: Ability, target_ids: list[str]) -> None:
        from wyrdfall.ui.screens.ability_challenge import AbilityChallengeScreen

        try:
            score = await self.app.push_screen_wait(AbilityChallengeScreen(ability.name, ability.challenge))
            await self._submit_action(ability.id, target_ids, score)
        finally:
            self._challenge_running = False

    async def _submit_action(self, ability_id: str, target_ids: list[str], challenge_score: float | None) -> None:
        client = self.app.client
        if client is not self._subscribed_client or client.is_paused:
            return
        state = client.get_combat_state()
        if state is None or state.is_over or state.pending_parry is not None:
            return
        actor_id = state.current_actor_id()
        if actor_id not in client.local_character_ids():
            return
        try:
            await client.submit_action(
                Action(actor_id=actor_id, ability_id=ability_id, target_ids=target_ids, challenge_score=challenge_score)
            )
        except Exception as exc:  # illegal actions are prevented by the UI, but stay safe
            self.query_one("#combat-log", RichLog).write(f"[bold red]! {escape(str(exc))}[/bold red]")
            self.handle_update()

    def write_log(self, lines: list[str]) -> None:
        log = self.query_one("#combat-log", RichLog)
        for line in lines:
            log.write(_colorize_log_line(line))

    async def finish_combat(self) -> None:
        await self.app.client.advance_after_combat()
        # Navigation happens reactively in handle_update, triggered by the
        # notify that call just fired (locally immediate, or on the next
        # broadcast for a remote client) -- see _navigate_away.

    async def _navigate_away(self) -> None:
        client = self.app.client
        if client is None or getattr(self.app, "_leaving_run", False):
            return
        summary = client.get_last_summary()
        if summary is not None:
            from wyrdfall.ui.screens.run_summary import RunSummaryScreen

            ecos_earned = self.app.bank_run_reward()
            while len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            self.app.push_screen(RunSummaryScreen(summary, ecos_earned))
        else:
            self.app.pop_screen()  # victory, dungeon continues -- back to DungeonScreen
