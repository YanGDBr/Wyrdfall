"""Runas como drops + Forja de Campo "combinar 2 runas" + Ferreiro "craftar
runas" (docs/design/08-itens-crafting.md) -- the scarcity the rune system
lacked until now."""

import random

import pytest

from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.items import Rarity
from wyrdfall.domain.loot import roll_rune_drop
from wyrdfall.domain.run import RunState
from wyrdfall.domain.runes import RUNE_DEFS, RUNE_DROP_POOL
from wyrdfall.domain.smith import RECIPE_DEFS
from wyrdfall.engine.session import COMBINE_RUNES_FRAGMENTOS_COST, GameSession
from wyrdfall.persistence.store import MetaProgressionState


def _session(encounters=None, seed=1):
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=encounters or [EncounterDef(id="e", name="e", enemy_ids=["goblin"])])
    return GameSession(RunState(run_id="r", seed=seed, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)


def test_every_base_rune_has_a_tier_two_twin_with_doubled_numbers():
    base = [r for r in RUNE_DEFS.values() if r.tier == 1]
    assert len(base) == 7 and set(RUNE_DROP_POOL) == {r.id for r in base}
    for rune in base:
        twin = RUNE_DEFS[rune.upgrades_to]
        assert twin.tier == 2 and twin.upgrades_to is None and twin.name == f"{rune.name} II"
        for a, b in zip(rune.modifiers, twin.modifiers):
            assert b.stat == a.stat and b.value == pytest.approx(a.value * 2)
        for a, b in zip(rune.triggered_effects, twin.triggered_effects):
            assert b.trigger == a.trigger and b.effect.amount == pytest.approx(a.effect.amount * 2)


def test_a_rune_must_be_owned_to_be_socketed_and_returns_on_unsocket():
    session = _session()
    hero = session.run.party[0]
    assert session.socket_rune("hero", "rune_might") is False  # not owned
    session.run.rune_inventory = ["rune_might"]
    assert session.socket_rune("hero", "rune_might") is True
    assert session.run.rune_inventory == []
    assert session.socket_rune("hero", "rune_might", ability_id="strike") is False  # the one copy is in use
    assert session.unsocket_rune("hero", "rune_might") is True
    assert session.run.rune_inventory == ["rune_might"] and hero.body_rune_slots == []


def test_bosses_always_drop_a_rune_and_normal_fights_sometimes_do():
    boss = EncounterDef(id="b", name="b", enemy_ids=["goblin"], is_boss=True)
    assert roll_rune_drop(boss, 0, random.Random(3), RUNE_DROP_POOL) in RUNE_DROP_POOL
    normal = EncounterDef(id="n", name="n", enemy_ids=["goblin"])
    results = {roll_rune_drop(normal, 0, random.Random(seed), RUNE_DROP_POOL) for seed in range(40)}
    assert None in results and any(r in RUNE_DROP_POOL for r in results)
    assert roll_rune_drop(boss, 0, random.Random(3), []) is None


def test_winning_a_boss_puts_a_rune_in_the_pouch():
    session = _session(encounters=[EncounterDef(id="b", name="b", enemy_ids=["goblin"], is_boss=True)])
    state = session.start_current_encounter()
    state.combatants["goblin_0"].current_hp = 0.0
    session.combat_engine._check_victory(state)
    session.collect_victory_reward_and_advance()
    assert len(session.run.rune_inventory) == 1 and session.run.rune_inventory[0] in RUNE_DROP_POOL


def test_combining_two_copies_at_the_forge_costs_fragments_and_a_common_material():
    session = _session(encounters=[EncounterDef(id="forge", name="Forja", room_type="forge")])
    session.run.rune_inventory = ["rune_might"]
    session.run.currency_earned = COMBINE_RUNES_FRAGMENTOS_COST
    session.run.materials = {Rarity.COMUM: 1}
    assert session.combine_runes("rune_might") is False  # needs two
    session.run.rune_inventory.append("rune_might")
    session.run.materials = {}
    assert session.combine_runes("rune_might") is False  # needs the material
    session.run.materials = {Rarity.COMUM: 1}
    session.run.currency_earned = COMBINE_RUNES_FRAGMENTOS_COST - 1
    assert session.combine_runes("rune_might") is False  # needs the Fragmentos
    session.run.currency_earned = COMBINE_RUNES_FRAGMENTOS_COST
    assert session.combine_runes("rune_might") is True
    assert session.run.rune_inventory == ["rune_might_2"]
    assert session.run.currency_earned == 0 and session.run.materials[Rarity.COMUM] == 0
    assert session.combine_runes("rune_might_2") is False  # tier 2 is the ceiling

    hero = session.run.party[0]
    before = hero.computed_stats(session.ruleset).attack
    assert session.socket_rune("hero", "rune_might_2") is True
    assert hero.computed_stats(session.ruleset).attack == pytest.approx(before + 6)


def test_the_smith_crafts_a_starting_rune_that_every_run_begins_with(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    recipe = RECIPE_DEFS["craft_rune_might"]
    assert recipe.grants_rune_id == "rune_might"
    meta = MetaProgressionState()
    meta.ecos = recipe.cost_ecos
    meta.materials = {Rarity.COMUM: 1}
    assert meta.craft("craft_rune_might") is True
    assert meta.starting_runes == ["rune_might"]

    app = WyrdfallApp()
    app.meta.starting_runes = ["rune_might"]
    client = app.start_new_run()
    assert client.get_run().rune_inventory == ["rune_might"]


@pytest.mark.asyncio
async def test_the_forge_screen_offers_the_combine_button(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "forge")
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.forge import ForgeScreen

    app = WyrdfallApp()
    async with app.run_test(size=(100, 250)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        run = app.client.get_run()
        run.rune_inventory = ["rune_haste", "rune_haste"]
        run.currency_earned = COMBINE_RUNES_FRAGMENTOS_COST
        run.materials = {Rarity.COMUM: 1}
        run.encounter_index = next(i for i, e in enumerate(app.client.get_dungeon().encounters) if e.room_type == "special")
        app.screen.refresh_dungeon()
        await pilot.pause()
        await pilot.click("#enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, ForgeScreen)
        await pilot.click("#combine_rune_haste")
        await pilot.pause(0.3)
        assert run.rune_inventory == ["rune_haste_2"]
        assert not list(app.screen.query("#combine_rune_haste"))
