"""Versioned profile data in SQLite, including durable reward receipts.

Legacy fields load through model defaults. Reward transactions persist
the complete profile and receipt together; future versions are rejected.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from wyrdfall.domain.content.permanent_trees import PERMANENT_TREE_COST, PERMANENT_TREES
from wyrdfall.domain.companions import COMPANION_DEFS
from wyrdfall.domain.guild_missions import GUILD_MISSION_DEFS, MissionProgressInput
from wyrdfall.domain.items import Rarity
from wyrdfall.domain.pacts import PACT_DEFS, PACT_SLOT_COST, VANTAGEM_SLOTS_BASE
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.domain.smith import RECIPE_DEFS
from wyrdfall.domain.wyrd import ASCENSION_MAX
from wyrdfall.persistence.paths import save_db_path


class RunSummary(BaseModel):
    run_id: str
    class_id: str
    floor_reached: int
    victory: bool
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


PARRY_COST = 15
# Fase 7 -- docs/design/14-estrutura-da-run.md §3, Portão Submerso's
# "Ecos + ter vencido a run ao menos uma vez". First-guess cost, same
# spirit as PARRY_COST -- adjustable in balancing.
PORTAL_SUBMERSO_COST = 20


class MetaProgressionState(BaseModel):
    schema_version: int = 1
    processed_runs: dict[str, int] = Field(default_factory=dict)
    ecos: int = 0
    bonus_talent_points: int = 0
    best_floor_reached: int = 0
    run_history: list[RunSummary] = Field(default_factory=list)
    can_parry: bool = False
    fast_combat: bool = False
    alt_palette: bool = False
    # 09-roadmap.md decision 7: remappable keys (domain/keybindings.py) --
    # only the overrides are stored; "" means deliberately unbound.
    keybindings: dict[str, str] = Field(default_factory=dict)
    # the main menu nudges toward the Tutorial until it has been read once
    tutorial_seen: bool = False
    unlocked_races: set[str] = Field(default_factory=lambda: {"human"})
    # races whose in-run evolution has happened at least once (04-racas.md
    # Meio-celestial's prestige gate: "desbloqueado e evoluído")
    evolved_races: set[str] = Field(default_factory=set)
    active_race_id: str = "human"
    completed_conquests: set[str] = Field(default_factory=set)
    discovered_enemies: set[str] = Field(default_factory=set)
    # Fase 5c -- docs/design/10-sistemas-de-build.md §6. tree id -> allocated
    # node ids. Permanent, like the other progression trees: no desalocar.
    permanent_tree_allocated: dict[str, set[str]] = Field(default_factory=dict)
    # Fase 7 -- feeds Renascido's unlock (domain/races.py::
    # check_meta_race_unlock). Deliberately its own always-accumulating
    # counter rather than derived from run_history, which is capped to
    # the last 20 runs and so can't answer "total ever".
    total_deaths: int = 0
    # Fase 9 -- Companheiro/Familiar (domain/companions.py): bought once
    # with Ecos, one picked (or none) for the next run. A slot of its own,
    # never one of the Active Ability Slots.
    unlocked_companions: set[str] = Field(default_factory=set)
    active_companion_id: str | None = None
    # 08-itens-crafting.md: materials persist between runs ("não zera na
    # morte") and feed the Ferreiro; starting_gear is what every future
    # run begins with in its inventory; missions are the long-term chains.
    materials: dict[Rarity, int] = Field(default_factory=dict)
    starting_gear: list[str] = Field(default_factory=list)
    starting_runes: list[str] = Field(default_factory=list)
    crafted_recipes: list[str] = Field(default_factory=list)
    bosses_defeated_ids: set[str] = Field(default_factory=set)
    risk_free_victories: int = 0
    completed_missions: set[str] = Field(default_factory=set)
    # Fase 7 -- feeds Portão Submerso's unlock (buy_portal_unlock below).
    # Same "own always-accumulating counter, not derived from run_history"
    # reasoning as total_deaths above -- run_history is capped to the
    # last 20 runs, which can't answer "ever won at least once".
    total_victories: int = 0
    unlocked_portals: set[str] = Field(
        default_factory=lambda: {"portao_do_tumulo", "portao_da_fornalha", "portao_do_gelo", "portao_da_tempestade"}
    )
    # Fase 8 -- Pactos do Wyrd (docs/design/06-economia-progressao.md): bought
    # once, equipped freely as a loadout; Vantagens capped by slots, Riscos
    # not. Ascensão (roadmap decision 5) opens on the first victory.
    unlocked_pacts: set[str] = Field(default_factory=set)
    equipped_pacts: list[str] = Field(default_factory=list)
    vantagem_slots: int = VANTAGEM_SLOTS_BASE
    ascension_unlocked: bool = False
    ascension_level: int = 0

    def cost_for_next_talent_point(self) -> int:
        return 3 + 2 * self.bonus_talent_points

    def buy_bonus_talent_point(self) -> bool:
        cost = self.cost_for_next_talent_point()
        if self.ecos < cost:
            return False
        self.ecos -= cost
        self.bonus_talent_points += 1
        return True

    def buy_parry(self) -> bool:
        if self.can_parry or self.ecos < PARRY_COST:
            return False
        self.ecos -= PARRY_COST
        self.can_parry = True
        return True

    def unlock_race(self, race_id: str) -> bool:
        if race_id in self.unlocked_races:
            return False
        self.unlocked_races.add(race_id)
        return True

    def evolved_race_count(self) -> int:
        return len(self.evolved_races & self.unlocked_races)

    def can_buy_race(self, race_id: str) -> bool:
        race = RACE_DEFS.get(race_id)
        if race is None or race.prestige_cost is None or race_id in self.unlocked_races:
            return False
        return self.ecos >= race.prestige_cost and self.evolved_race_count() >= race.prestige_evolved_races_required

    def buy_race(self, race_id: str) -> bool:
        if not self.can_buy_race(race_id):
            return False
        self.ecos -= RACE_DEFS[race_id].prestige_cost or 0
        self.unlocked_races.add(race_id)
        return True

    def discover_enemy(self, enemy_id: str) -> bool:
        if enemy_id in self.discovered_enemies:
            return False
        self.discovered_enemies.add(enemy_id)
        return True

    def allocate_permanent_node(self, tree_id: str, node_id: str) -> bool:
        tree = PERMANENT_TREES.get(tree_id)
        if tree is None or node_id not in tree.nodes or self.ecos < PERMANENT_TREE_COST:
            return False
        allocated = self.permanent_tree_allocated.setdefault(tree_id, set())
        if not tree.can_allocate(node_id, allocated):
            return False
        self.ecos -= PERMANENT_TREE_COST
        allocated.add(node_id)
        return True

    def complete_conquest(self, conquest_id: str, ecos_reward: int) -> int:
        if conquest_id in self.completed_conquests:
            return 0
        self.completed_conquests.add(conquest_id)
        self.ecos += ecos_reward
        return ecos_reward

    def record_run(
        self, summary: RunSummary, ecos_earned: int, *,
        boss_ids: list[str] | None = None, used_risk_pact: bool = False,
        materials: dict[Rarity, int] | None = None,
    ) -> None:
        if summary.run_id in self.processed_runs:
            return
        self.processed_runs[summary.run_id] = ecos_earned
        self.ecos += ecos_earned
        self.run_history.append(summary)
        self.run_history = self.run_history[-20:]
        self.best_floor_reached = max(self.best_floor_reached, summary.floor_reached)
        if summary.victory:
            self.total_victories += 1
            self.ascension_unlocked = True  # docs/design/14-estrutura-da-run.md §9
            if not used_risk_pact:
                self.risk_free_victories += 1
        else:
            self.total_deaths += 1
        self.bosses_defeated_ids.update(boss_ids or [])
        # materials persist whether the run was won or lost (08-itens-crafting.md)
        for rarity, count in (materials or {}).items():
            self.materials[rarity] = self.materials.get(rarity, 0) + count

    # -- ferreiro (docs/design/08-itens-crafting.md) --------------------------------

    def can_craft(self, recipe_id: str) -> bool:
        recipe = RECIPE_DEFS.get(recipe_id)
        if recipe is None or recipe_id in self.crafted_recipes or self.ecos < recipe.cost_ecos:
            return False
        if recipe.unlocks_race and recipe.unlocks_race in self.unlocked_races:
            return False
        return all(self.materials.get(rarity, 0) >= count for rarity, count in recipe.cost_materials.items())

    def craft(self, recipe_id: str) -> bool:
        """Pays Ecos + persistent materials once; a gear recipe adds its item
        to starting_gear, the Construto recipe unlocks the race."""
        if not self.can_craft(recipe_id):
            return False
        recipe = RECIPE_DEFS[recipe_id]
        self.ecos -= recipe.cost_ecos
        for rarity, count in recipe.cost_materials.items():
            self.materials[rarity] -= count
        self.crafted_recipes.append(recipe_id)
        if recipe.grants_item_id:
            self.starting_gear.append(recipe.grants_item_id)
        if recipe.grants_rune_id:
            self.starting_runes.append(recipe.grants_rune_id)
        if recipe.unlocks_race:
            self.unlock_race(recipe.unlocks_race)
        return True

    # -- missões da guilda (docs/design/08-itens-crafting.md) -------------------------

    def mission_progress_input(self) -> MissionProgressInput:
        return MissionProgressInput(
            bosses_defeated_ids=set(self.bosses_defeated_ids),
            runs_finished=self.total_victories + self.total_deaths,
            risk_free_victories=self.risk_free_victories,
        )

    def complete_missions(self) -> list[str]:
        """Completes every mission whose chain is done and applies its one
        big unlock; returns the newly completed ids."""
        data = self.mission_progress_input()
        completed = []
        for mission in GUILD_MISSION_DEFS.values():
            if mission.id in self.completed_missions or not mission.is_complete(data):
                continue
            self.completed_missions.add(mission.id)
            if mission.reward_kind == "portal":
                self.unlocked_portals.add(mission.reward_id)
            elif mission.reward_kind == "companion":
                self.unlocked_companions.add(mission.reward_id)
            elif mission.reward_kind == "vantagem_slot":
                self.vantagem_slots += 1
            completed.append(mission.id)
        return completed

    def buy_pact(self, pact_id: str) -> bool:
        pact = PACT_DEFS.get(pact_id)
        if pact is None or pact_id in self.unlocked_pacts or self.ecos < pact.cost:
            return False
        self.ecos -= pact.cost
        self.unlocked_pacts.add(pact_id)
        return True

    def toggle_pact(self, pact_id: str) -> bool:
        """Equips or unequips an unlocked pact. Vantagens are capped by
        vantagem_slots; Pactos de Risco are not -- turning on more of them
        is the whole point."""
        pact = PACT_DEFS.get(pact_id)
        if pact is None or pact_id not in self.unlocked_pacts:
            return False
        if pact_id in self.equipped_pacts:
            self.equipped_pacts.remove(pact_id)
            return True
        if pact.kind == "vantagem":
            equipped_vantagens = sum(1 for pid in self.equipped_pacts if PACT_DEFS[pid].kind == "vantagem")
            if equipped_vantagens >= self.vantagem_slots:
                return False
        self.equipped_pacts.append(pact_id)
        return True

    def buy_vantagem_slot(self) -> bool:
        if self.ecos < PACT_SLOT_COST:
            return False
        self.ecos -= PACT_SLOT_COST
        self.vantagem_slots += 1
        return True

    def buy_companion(self, companion_id: str) -> bool:
        companion = COMPANION_DEFS.get(companion_id)
        if companion is None or companion_id in self.unlocked_companions or self.ecos < companion.cost:
            return False
        self.ecos -= companion.cost
        self.unlocked_companions.add(companion_id)
        return True

    def set_active_companion(self, companion_id: str | None) -> bool:
        """None leaves the slot empty -- a companion is optional."""
        if companion_id is not None and companion_id not in self.unlocked_companions:
            return False
        self.active_companion_id = companion_id
        return True

    def set_ascension_level(self, level: int) -> bool:
        if not self.ascension_unlocked or not (0 <= level <= ASCENSION_MAX):
            return False
        self.ascension_level = level
        return True

    def buy_portal_unlock(self, portal_id: str) -> bool:
        if portal_id in self.unlocked_portals:
            return False
        if self.total_victories < 1 or self.ecos < PORTAL_SUBMERSO_COST:
            return False
        self.ecos -= PORTAL_SUBMERSO_COST
        self.unlocked_portals.add(portal_id)
        return True


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta_progression ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL)"
    )
    conn.commit()


def load_meta_progression(db_path: Path | None = None) -> MetaProgressionState:
    with closing(sqlite3.connect(db_path or save_db_path())) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT data FROM meta_progression WHERE id = 1").fetchone()
        if row is None:
            return MetaProgressionState()
        state = MetaProgressionState.model_validate_json(row[0])
        if state.schema_version != 1:
            raise ValueError(f"Versão de save incompatível: {state.schema_version}")
        for summary in state.run_history:
            state.processed_runs.setdefault(summary.run_id, 0)
        return state


def save_meta_progression(state: MetaProgressionState, db_path: Path | None = None) -> None:
    with closing(sqlite3.connect(db_path or save_db_path())) as conn:
        _ensure_schema(conn)
        conn.execute(
            "INSERT INTO meta_progression (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (state.model_dump_json(),),
        )
        conn.commit()


def commit_run_progress(state: MetaProgressionState, run_id: str, db_path: Path | None = None) -> MetaProgressionState:
    """Commit the complete reward and its receipt together, once per profile.

    A repeated delivery from another app instance returns the stored result.
    Callers calculate on a copy so a failed write cannot leave memory credited.
    """
    if run_id not in state.processed_runs:
        raise ValueError("O resultado precisa conter o recibo da run.")
    with closing(sqlite3.connect(db_path or save_db_path())) as conn:
        _ensure_schema(conn)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT data FROM meta_progression WHERE id = 1").fetchone()
            if row is not None:
                saved = MetaProgressionState.model_validate_json(row[0])
                if saved.schema_version != 1:
                    raise ValueError("Versão de save incompatível.")
                if run_id in saved.processed_runs:
                    conn.rollback()
                    return saved
            conn.execute(
                "INSERT INTO meta_progression (id, data) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data", (state.model_dump_json(),),
            )
            conn.commit()
            return state
        except BaseException:
            conn.rollback()
            raise
