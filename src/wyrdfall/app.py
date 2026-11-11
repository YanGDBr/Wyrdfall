"""Textual application entrypoint and shared app-level state.

Screens read/mutate state off ``self.app`` (typed here as WyrdfallApp) rather
than owning it themselves. In particular they always dispatch through
``self.app.client`` (a :class:`~wyrdfall.net.game_client.GameClient`) rather
than a GameSession or a socket directly, so the same screens work whether
the app is running solo, hosting, or connected as a client -- only which
GameClient implementation is plugged in differs.
"""

from __future__ import annotations

import sqlite3

import random
import uuid

from textual.app import App

from wyrdfall.domain.character import Character
from wyrdfall.domain.companions import COMPANION_DEFS, build_companion
from wyrdfall.domain.conquests import CONQUEST_DEFS, check_conquests
from wyrdfall.domain.contracts import contract_offer_for
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_dungeon_for_portal, build_ruleset
from wyrdfall.domain.content.permanent_trees import PERMANENT_TREES
from wyrdfall.domain.economy import ecos_for_run
from wyrdfall.domain.loadout import PlayerLoadout, build_character_from_loadout
from wyrdfall.domain.models import Archetype, DamageElement, Modifier, TriggeredEffect
from wyrdfall.domain.pacts import PACT_DEFS
from wyrdfall.domain.races import RACE_DEFS, check_meta_race_unlock
from wyrdfall.domain.wyrd import reward_multiplier, starting_wyrd
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession
from wyrdfall.net.client import NetworkConnection
from wyrdfall.net.game_client import GameClient, LocalGameClient
from wyrdfall.net.server import HostServer
from wyrdfall.persistence.store import MetaProgressionState, commit_run_progress, load_meta_progression, save_meta_progression
from wyrdfall.ui.screens.main_menu import MainMenuScreen
from wyrdfall.ui.widgets import KIT_CSS


class WyrdfallApp(App):
    TITLE = "Wyrdfall"
    SUB_TITLE = "O Túmulo Oco"
    CSS = KIT_CSS + """
    Screen {
        align: center middle;
    }

    /* Every screen is a full-size frame: a one-line Header, a body that
       fills the rest, then the Footer. Panels (ui/widgets.py) live inside. */
    .frame {
        width: 100%;
        height: 100%;
        padding: 0 1;
    }
    .body {
        width: 100%;
        height: 1fr;
    }
    .body-scroll {
        width: 100%;
        height: 1fr;
    }
    .actions {
        height: auto;
        width: 100%;
        padding-top: 1;
    }

    .title {
        text-style: bold;
        color: $accent;
        content-align: center middle;
        width: 100%;
        padding-bottom: 1;
    }
    .subtitle {
        color: $text-muted;
        width: 100%;
        padding-bottom: 1;
    }
    .muted { color: $text-muted; }
    .big {
        text-style: bold;
        width: 100%;
    }
    .center { content-align: center middle; text-align: center; width: 100%; }

    Button {
        width: 100%;
    }
    Button.compact {
        height: 1;
        min-height: 1;
        border: none;
        margin: 0;
    }

    /* combat */
    #combat-root { width: 100%; height: 100%; }
    #combat-top { height: auto; max-height: 45%; width: 100%; }
    #combat-log { height: 1fr; }

    /* row lists inside scrolling panels size to their content, and their
       buttons are one-line rows (a list of ten options fits a small terminal) */
    VerticalScroll > Vertical { height: auto; }
    VerticalScroll > Vertical > Button { height: 1; min-height: 1; border: none; margin: 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.ruleset = build_ruleset()
        self.meta: MetaProgressionState = load_meta_progression()
        self.client: GameClient | None = None
        self.player_name: str = "Herói"
        self.host_server: HostServer | None = None
        self.net_connection: NetworkConnection | None = None

    def on_mount(self) -> None:
        self.apply_accessibility_settings()
        self.push_screen(MainMenuScreen())
        self.set_interval(0.25, self._refresh_connection_controls)

    def _refresh_connection_controls(self) -> None:
        from textual.widgets import Button
        paused = self.client is not None and self.client.is_paused
        restored = False
        for button in self.screen.query(Button):
            if button.id in ("save_exit", "abandon", "back", "done", "party-ready"):
                continue
            if paused and not hasattr(button, "_before_disconnect"):
                button._before_disconnect = button.disabled
                button.disabled = True
            elif not paused and hasattr(button, "_before_disconnect"):
                button.disabled = button._before_disconnect
                del button._before_disconnect
                restored = True
        if restored and self.client is not None:
            self.client._notify()  # recompute current costs/slots after restoring controls

    def saved_checkpoint(self):
        from wyrdfall.persistence.checkpoint import load_checkpoint
        try:
            return load_checkpoint()
        except (ValueError, OSError, sqlite3.Error):
            return None

    def save_host_checkpoint(self) -> None:
        from wyrdfall.persistence.checkpoint import RunCheckpoint
        server = self.host_server
        if server is not None and server.session is not None:
            self._write_checkpoint(RunCheckpoint.from_session(server.session, mode="host",
                player_id=server.host_player_id, player_name=self.player_name, port=server.port or 0,
                players=server.players, loadouts=server.loadouts, tokens=server.resume_tokens))

    def _write_checkpoint(self, snapshot) -> None:
        from wyrdfall.persistence.checkpoint import save_checkpoint, clear_checkpoint
        try:
            if snapshot.run.run_id in self.meta.processed_runs:
                clear_checkpoint(snapshot.run.run_id)
            else:
                save_checkpoint(snapshot)
            self._checkpoint_failed = False
        except (OSError, sqlite3.Error) as exc:
            self._checkpoint_failed = True
            self.notify(f"Não foi possível salvar a run: {exc}", severity="error")

    def save_client_checkpoint(self) -> None:
        from wyrdfall.persistence.checkpoint import RunCheckpoint
        from wyrdfall.net.remote_client import RemoteGameClient
        if isinstance(self.client, LocalGameClient):
            self._write_checkpoint(RunCheckpoint.from_session(self.client.session, mode="solo",
                player_id=next(iter(self.client.local_character_ids())), player_name=self.player_name))
        elif isinstance(self.client, RemoteGameClient):
            connection = self.client.connection
            self._write_checkpoint(RunCheckpoint(mode="guest", run=self.client.get_run(),
                dungeon=self.client.get_dungeon(), combat=self.client.get_combat_state(),
                summary=self.client.get_last_summary(), player_id=self.client.player_id,
                player_name=connection.player_name, uri=connection.uri, resume_token=connection.resume_token))
        elif self.host_server is not None:
            self.save_host_checkpoint()

    def attach_autosave(self) -> None:
        self.client.on_update(self.save_client_checkpoint)
        self.save_client_checkpoint()

    def report_run_error(self, message: str) -> None:
        self.notify(message, severity="warning")

    async def suspend_run(self) -> None:
        self._leaving_run = True
        try:
            self.save_client_checkpoint()
            if getattr(self, "_checkpoint_failed", False):
                raise OSError("A run continua aberta porque o autosave falhou. Tente salvar novamente.")
            await self.leave_multiplayer()
            self.show_main_menu()
        finally:
            self._leaving_run = False

    async def resume_saved_run(self, address: str = "") -> None:
        from wyrdfall.net.remote_client import RemoteGameClient
        from wyrdfall.net.host_client import HostGameClient
        from wyrdfall.net.protocol import ServerStateUpdate
        from wyrdfall.ui.screens.dungeon import DungeonScreen
        snapshot = self.saved_checkpoint()
        if snapshot is None:
            raise ValueError("Não há uma run salva compatível.")
        self.player_name = snapshot.player_name
        if snapshot.mode == "solo":
            self.client = LocalGameClient(snapshot.restore_session(self.ruleset), {snapshot.player_id})
            self.client._last_summary = snapshot.summary
        elif snapshot.mode == "host":
            port = int(address or snapshot.port)
            if not 0 <= port <= 65535:
                raise ValueError("Informe uma porta de 1 a 65535 ou use 0 para escolher automaticamente.")
            server = HostServer.from_checkpoint(snapshot, self.ruleset)
            await server.start(port=port)
            self.host_server = server
            server.checkpoint_callback = self.save_host_checkpoint
            self.client = HostGameClient(server)
        else:
            uri = address or snapshot.uri
            if not uri.startswith(("ws://", "wss://")):
                uri = "ws://" + uri
            connection = NetworkConnection(uri)
            connection.resume_token = snapshot.resume_token
            connection.run_id = snapshot.run.run_id
            connection.player_name = snapshot.player_name
            self.net_connection = connection
            self.client = RemoteGameClient(connection, self.ruleset, snapshot.player_id,
                ServerStateUpdate(run=snapshot.run, combat_state=snapshot.combat, summary=snapshot.summary,
                                  dungeon=snapshot.dungeon))
            self.client.on_error(self.report_run_error)
            connection.resume_in_background()
        self.attach_autosave()
        self.show_main_menu()
        self.push_screen(DungeonScreen())
        if self.host_server is not None:
            await self.host_server._broadcast_state()

    def apply_accessibility_settings(self) -> None:
        """Re-applies the current player's saved accessibility preferences --
        called on boot and again right after either is toggled in
        MetaProgressionScreen, so a change takes effect immediately."""
        self.theme = "solarized-dark" if self.meta.alt_palette else "textual-dark"

    def ai_turn_delay_seconds(self) -> float:
        return 0.15 if self.meta.fast_combat else 0.6

    # -- run lifecycle helpers -----------------------------------------------

    def build_loadout(
        self, class_id: str = "runeguard", sealed_archetypes: set[Archetype] | None = None,
        sealed_elements: set[DamageElement] | None = None,
    ) -> PlayerLoadout:
        """Everything this player's own Guild state contributes to their
        character (docs/design/14-estrutura-da-run.md §1) -- the solo hero
        is built from it directly, a co-op joiner sends it in ClientHello."""
        class_def = CLASS_DEFS[class_id]
        return PlayerLoadout(
            class_id=class_id,
            race_id=self.meta.active_race_id,
            sealed_archetypes=set(sealed_archetypes or set()),
            sealed_elements=set(sealed_elements or set()),
            can_parry=self.meta.can_parry,
            starting_gear=list(self.meta.starting_gear),
            starting_runes=list(self.meta.starting_runes),
            companion_id=self.meta.active_companion_id,
            bonus_talent_points=self.meta.bonus_talent_points,
            permanent_modifiers=self._permanent_tree_modifiers(class_def.base_archetype.value),
            permanent_triggered_effects=self._permanent_tree_triggered_effects(class_def.base_archetype.value),
        )

    def build_hero(
        self, character_id: str, name: str, class_id: str = "runeguard", sealed_archetypes: set[Archetype] | None = None,
        sealed_elements: set[DamageElement] | None = None,
    ) -> Character:
        return build_character_from_loadout(
            character_id, name, self.build_loadout(class_id, sealed_archetypes, sealed_elements), self.ruleset,
            pacts=self.meta.equipped_pacts,
        )

    def _permanent_tree_modifiers(self, base_archetype_id: str) -> list[Modifier]:
        """Resolves the player's own race tree + their chosen archetype's
        tree allocations (Fase 5c, MetaProgressionState.
        permanent_tree_allocated) into Modifiers -- same "look up once at
        creation" pattern race_modifiers_for(character.race_id) already
        uses, just sourced from meta state instead of a fixed race lookup."""
        modifiers = []
        for tree_id in (f"permanent_{self.meta.active_race_id}", f"permanent_{base_archetype_id}"):
            tree = PERMANENT_TREES.get(tree_id)
            if tree is None:
                continue
            allocated = self.meta.permanent_tree_allocated.get(tree_id, set())
            modifiers.extend(tree.modifiers_for(allocated))
        return modifiers

    def _permanent_tree_triggered_effects(self, base_archetype_id: str) -> list[TriggeredEffect]:
        effects: list[TriggeredEffect] = []
        for tree_id in (f"permanent_{self.meta.active_race_id}", f"permanent_{base_archetype_id}"):
            tree = PERMANENT_TREES.get(tree_id)
            if tree is None:
                continue
            allocated = self.meta.permanent_tree_allocated.get(tree_id, set())
            effects.extend(tree.triggered_effects_for(allocated))
        return effects

    def start_new_run(
        self,
        class_id: str = "runeguard",
        sealed_archetypes: set[Archetype] | None = None,
        portal_id: str = "portao_do_tumulo",
        sealed_elements: set[DamageElement] | None = None,
    ) -> GameClient:
        """Solo mode: a single-player run driven entirely in-process."""
        hero = self.build_hero(
            "hero", self.player_name, class_id=class_id, sealed_archetypes=sealed_archetypes, sealed_elements=sealed_elements,
        )
        dungeon = build_dungeon_for_portal(portal_id)
        run = RunState(
            run_id=uuid.uuid4().hex[:8],
            seed=random.randint(0, 2**31 - 1),
            dungeon_id=dungeon.id,
            party=[hero],
            active_pacts=list(self.meta.equipped_pacts),
            ascension_level=self.meta.ascension_level,
            wyrd_meter=starting_wyrd(self.meta.equipped_pacts),
            companions=self.build_companions(hero),
        )
        run.contract_offer = contract_offer_for(run.seed)
        from wyrdfall.domain.inventory import add_equipment
        for definition_id in self.meta.starting_gear:
            add_equipment(run, definition_id, owner_id=run.party[0].id)
        run.rune_inventory = list(self.meta.starting_runes)
        session = GameSession(run, self.ruleset, TALENT_TREES, dungeon=dungeon)
        self.client = LocalGameClient(session)
        self.attach_autosave()
        return self.client

    def build_companions(self, owner: Character) -> list[Character]:
        """Fase 9: the Guild's active Companheiro, attached to this owner."""
        companion_def = COMPANION_DEFS.get(self.meta.active_companion_id or "")
        return [build_companion(companion_def, owner)] if companion_def is not None else []

    def discover_enemies_in_current_encounter(self) -> None:
        """Discover encountered enemies from the shared run in every mode."""
        if self.client is None:
            return
        # A list comprehension, not any(generator) -- discover_enemy must run
        # for every enemy_id, not stop at the first newly-discovered one.
        newly_discovered = any([self.meta.discover_enemy(enemy_id) for enemy_id in self.client.get_run().discovered_enemy_ids])
        if newly_discovered:
            self.save_progress()

    def bank_run_reward(self) -> int:
        assert self.client is not None
        summary = self.client.get_last_summary()
        if summary is None:
            return 0
        if summary.run_id in self.meta.processed_runs:
            from wyrdfall.persistence.checkpoint import clear_checkpoint
            clear_checkpoint(summary.run_id)
            return self.meta.processed_runs[summary.run_id]
        original = self.meta
        original_missions = getattr(self, "newly_completed_missions", [])
        self.meta = original.model_copy(deep=True)
        try:
            self._apply_run_reward()
            self.meta = commit_run_progress(self.meta, summary.run_id)
        except BaseException:
            self.meta = original
            self.newly_completed_missions = original_missions
            raise
        from wyrdfall.persistence.checkpoint import clear_checkpoint
        clear_checkpoint(summary.run_id)
        return self.meta.processed_runs[summary.run_id]

    def _apply_run_reward(self) -> int:
        """Applies the just-finished run's reward to this player's own
        local meta-progression save and persists it. Called identically
        after a solo run, by the host after its own run, and by each
        joiner after receiving the final state from the host -- everyone
        banks the same reward to their own save file. Returns the total
        Ecos earned (run formula + any newly-completed Conquistas) so the
        caller can show it on the summary screen."""
        assert self.client is not None
        summary = self.client.get_last_summary()
        if summary is None:
            return 0
        if summary.run_id in self.meta.processed_runs:
            return self.meta.processed_runs[summary.run_id]
        run = self.client.get_run()
        local_hero = next((hero for hero in run.party if hero.id in self.client.local_character_ids()), None)
        if local_hero is not None:
            summary = summary.model_copy(update={"class_id": local_hero.class_id})
        self.meta.discovered_enemies.update(run.discovered_enemy_ids)
        # Fase 8: Pactos de Risco / Ascensão / Medidor do Wyrd pay out here too
        ecos_earned = round(
            ecos_for_run(
                floors_completed=summary.floor_reached,
                bosses_defeated=run.bosses_defeated,
                fragments_remaining=run.currency_earned,
            )
            * reward_multiplier(run)
        ) + run.contract_ecos  # Contratos de Run pay their Ecos here
        used_risk_pact = any(PACT_DEFS[pid].kind == "risco" for pid in run.active_pacts if pid in PACT_DEFS)
        self.meta.record_run(
            summary, ecos_earned=ecos_earned,
            boss_ids=list(run.defeated_boss_ids), used_risk_pact=used_risk_pact, materials=dict(run.materials),
        )
        for race_id in run.race_unlocks:  # Fada's Portal Feérico, etc.
            self.meta.unlock_race(race_id)
        for character_id in self.client.local_character_ids():
            for race_id in run.race_unlocks_by_character.get(character_id, set()):
                self.meta.unlock_race(race_id)
        for character in run.party:  # Meio-celestial's prestige gate counts evolved races
            if character.id in self.client.local_character_ids() and character.race_evolved_this_run:
                self.meta.evolved_races.add(character.race_id)
        # Fase 7 -- meta-level unlocks (Renascido's total-deaths count),
        # distinct from the per-encounter-win check above: evaluated
        # once per finished run, for every race, regardless of victory.
        for race_id in RACE_DEFS:
            if race_id not in self.meta.unlocked_races and check_meta_race_unlock(
                race_id, total_deaths=self.meta.total_deaths
            ):
                self.meta.unlock_race(race_id)
        for conquest_id in check_conquests(run, summary, self.meta):
            ecos_earned += self.meta.complete_conquest(conquest_id, CONQUEST_DEFS[conquest_id].ecos_reward)
        self.newly_completed_missions = self.meta.complete_missions()
        self.meta.processed_runs[summary.run_id] = ecos_earned
        return ecos_earned

    def save_progress(self) -> None:
        save_meta_progression(self.meta)

    async def abandon_run(self) -> None:
        if self.client is None or getattr(self, "_leaving_run", False):
            return
        self._leaving_run = True
        try:
            await self.client.abandon_run()
            self.bank_run_reward()
            await self.leave_multiplayer()
            self.show_main_menu()
        finally:
            self._leaving_run = False

    async def leave_multiplayer(self) -> None:
        """Tears down whichever networking role is active (host or joiner)
        and drops the current GameClient. Safe to call unconditionally --
        a solo game just has nothing to tear down."""
        if self.client is not None:
            self.client.off_update(self.save_client_checkpoint)
            self.client.close()
        if self.host_server is not None:
            await self.host_server.stop()
            self.host_server = None
        if self.net_connection is not None:
            await self.net_connection.close()
            self.net_connection = None
        self.client = None

    def show_main_menu(self) -> None:
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(MainMenuScreen())


def run() -> None:
    WyrdfallApp().run()
