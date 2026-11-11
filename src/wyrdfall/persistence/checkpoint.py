"""Atomic, versioned snapshots of an unfinished run and its reconnect credentials."""
from __future__ import annotations

import random
import sqlite3
from contextlib import closing
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from wyrdfall.domain.combat import CombatEngine, CombatState
from wyrdfall.domain.dungeon import DungeonDef
from wyrdfall.domain.loadout import PlayerLoadout
from wyrdfall.domain.run import RunState
from wyrdfall.persistence import store
from wyrdfall.persistence.store import RunSummary


class RunCheckpoint(BaseModel):
    schema_version: Literal[2] = 2
    mode: Literal["solo", "host", "guest"]
    run: RunState
    dungeon: DungeonDef
    combat: CombatState | None = None
    rng_state: Any = None
    summary: RunSummary | None = None
    newly_eligible_races: list[str] = Field(default_factory=list)
    player_id: str = "hero"
    player_name: str = "Herói"
    uri: str = ""
    resume_token: str = ""
    port: int = 0
    players: dict[str, str] = Field(default_factory=dict)
    loadouts: dict[str, PlayerLoadout] = Field(default_factory=dict)
    tokens: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_v1(cls, value):
        if not isinstance(value, dict) or "run" not in value:
            return value
        version = value.get("schema_version", 1 if isinstance(value["run"], dict) else 2)
        if version == 1:
            value = dict(value)
            value["schema_version"] = 2
            # Migrate identities together, retaining combat health/turn/RNG.
            run = RunState.model_validate(value["run"])
            from wyrdfall.domain.inventory import initialize_weapons
            initialize_weapons(run)
            combat = value.get("combat")
            if isinstance(combat, dict):
                import copy
                combat = copy.deepcopy(combat)
                for hero in run.party:
                    actor = combat.get("combatants", {}).get(hero.id)
                    if actor is not None:
                        for field in ("equipped_armor", "equipped_accessories", "equipped_weapon_id", "equipment_instances", "item_enchantments"):
                            actor[field] = hero.model_dump(mode="json")[field]
                value["combat"] = combat
            value["run"] = run
        return value

    @classmethod
    def from_session(cls, session, **metadata):
        return cls(run=session.run, dungeon=session.dungeon, combat=session.combat_state,
                   rng_state=session.combat_engine.rng.getstate() if session.combat_engine else None,
                   summary=session._final_summary, newly_eligible_races=session.newly_eligible_races,
                   **metadata)

    def restore_session(self, ruleset):
        from wyrdfall.domain.content import TALENT_TREES
        from wyrdfall.engine.session import GameSession
        session = GameSession(self.run.model_copy(deep=True), ruleset, TALENT_TREES, self.dungeon)
        session.combat_state = self.combat.model_copy(deep=True) if self.combat else None
        session._final_summary = self.summary
        session.newly_eligible_races = list(self.newly_eligible_races)
        if session.combat_state is not None:
            rng = random.Random()
            if self.rng_state is not None:
                def tuples(value):
                    return tuple(tuples(v) for v in value) if isinstance(value, (list, tuple)) else value
                rng.setstate(tuples(self.rng_state))
            session.combat_engine = CombatEngine(ruleset, rng=rng)
            if session.combat_engine.recover_turn(session.combat_state):
                session._sync_party_from_combat()
        return session


def _schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS active_run (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")


def save_checkpoint(snapshot: RunCheckpoint) -> None:
    data = snapshot.model_dump_json()
    with closing(sqlite3.connect(store.save_db_path())) as conn:
        _schema(conn)
        conn.execute("INSERT INTO active_run(id,data) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (data,))
        conn.commit()


def load_checkpoint() -> RunCheckpoint | None:
    with closing(sqlite3.connect(store.save_db_path())) as conn:
        _schema(conn)
        row = conn.execute("SELECT data FROM active_run WHERE id=1").fetchone()
    return RunCheckpoint.model_validate_json(row[0]) if row else None


def clear_checkpoint(run_id: str) -> None:
    with closing(sqlite3.connect(store.save_db_path())) as conn:
        _schema(conn)
        row = conn.execute("SELECT data FROM active_run WHERE id=1").fetchone()
        if row and RunCheckpoint.model_validate_json(row[0]).run.run_id == run_id:
            conn.execute("DELETE FROM active_run WHERE id=1")
        conn.commit()
