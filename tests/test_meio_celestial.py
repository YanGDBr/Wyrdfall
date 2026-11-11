"""Meio-celestial (docs/design/04-racas.md, the prestige race shipped
last on purpose) + Avatar Dividido (05b-classes-roster.md §8)."""

import pytest

from wyrdfall.domain.combat import Action, CombatError
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.content.permanent_trees import PERMANENT_TREES
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Archetype, DamageElement, Effect, EffectKind, Modifier, ModifierKind, Stat, element_tag
from wyrdfall.domain.races import MEIO_CELESTIAL_COST, RACE_DEFS
from wyrdfall.domain.run import RunState
from wyrdfall.domain.specializations import SPECIALIZATION_DEFS, qualifying_specializations
from wyrdfall.engine.session import GameSession
from wyrdfall.persistence.store import MetaProgressionState


def _session(class_id="mistico", race_id="meio_celestial", permanent_modifiers=None):
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, race_id=race_id, permanent_modifiers=permanent_modifiers or [],
    )
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e", name="e", enemy_ids=["goblin"])])
    return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)


def test_the_race_exists_with_its_dual_nature_and_no_in_run_evolution():
    race = RACE_DEFS["meio_celestial"]
    assert race.prestige_cost == MEIO_CELESTIAL_COST and race.prestige_evolved_races_required == 2
    assert set(race.granted_abilities) == {"assumir_forma_sagrada", "assumir_forma_sombria"}
    assert "permanent_meio_celestial" in PERMANENT_TREES
    assert len(RACE_DEFS) == 9


def test_switching_form_is_once_per_combat_and_boosts_that_element_only():
    session = _session()
    state = session.start_current_encounter()
    engine = session.combat_engine
    hero = state.combatants["hero"]
    legal = {a.id for a in engine.legal_abilities(state, "hero")}
    assert {"assumir_forma_sagrada", "assumir_forma_sombria"} <= legal
    shadow_resist_before = hero.computed_stats(session.ruleset).shadow_resist
    elemental_before = hero.computed_stats(session.ruleset).elemental_damage_percent

    session.submit_action(Action(actor_id="hero", ability_id="assumir_forma_sagrada"))
    assert hero.active_transform_id == "forma_sagrada"
    assert hero.element_damage_bonus(session.ruleset, DamageElement.HOLY) == pytest.approx(0.40)
    assert hero.element_damage_bonus(session.ruleset, DamageElement.SHADOW) == 0.0
    assert hero.computed_stats(session.ruleset).shadow_resist == pytest.approx(shadow_resist_before - 0.20)
    # the +40% is per element, never on the general stat
    assert hero.computed_stats(session.ruleset).elemental_damage_percent == pytest.approx(elemental_before)

    # one switch per combat
    state.turn_index = state.turn_order.index("hero")
    with pytest.raises(CombatError):
        engine.resolve(state, Action(actor_id="hero", ability_id="assumir_forma_sagrada"))


def test_the_permanent_tree_allows_a_second_switch_and_the_form_swaps():
    extra = PERMANENT_TREES["permanent_meio_celestial"].modifiers_for({"permanent_meio_celestial_1"})
    session = _session(permanent_modifiers=extra)
    state = session.start_current_encounter()
    engine = session.combat_engine
    hero = state.combatants["hero"]
    session.submit_action(Action(actor_id="hero", ability_id="assumir_forma_sagrada"))
    state.turn_index = state.turn_order.index("hero")
    engine.resolve(state, Action(actor_id="hero", ability_id="assumir_forma_sombria"))
    assert hero.active_transform_id == "forma_sombria"
    assert hero.element_damage_bonus(session.ruleset, DamageElement.SHADOW) == pytest.approx(0.40)
    assert hero.element_damage_bonus(session.ruleset, DamageElement.HOLY) == 0.0
    # the form ends with the fight
    state.combatants["goblin_0"].current_hp = 0.0
    engine._check_victory(state)
    session.collect_victory_reward_and_advance()
    assert session.run.party[0].active_transform_id is None
    assert session.run.party[0].transformed_this_run is True


def test_element_tagged_modifiers_multiply_only_matching_hits():
    session = _session(class_id="runeguard", race_id="human")
    state = session.start_current_encounter()
    engine = session.combat_engine
    hero = state.combatants["hero"]
    goblin = state.combatants["goblin_0"]
    goblin.base_stats.max_hp = 10_000
    goblin.current_hp = 10_000
    hero.base_stats.crit_chance = 0.0

    holy = Effect(kind=EffectKind.DAMAGE, amount=100.0, damage_element=DamageElement.HOLY)
    engine._apply_effect(state, "hero", "goblin_0", holy)
    plain = 10_000 - goblin.current_hp
    goblin.current_hp = 10_000
    hero.transform_modifiers = [
        Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.40, source="t", tags=[element_tag(DamageElement.HOLY)])
    ]
    engine._apply_effect(state, "hero", "goblin_0", holy)
    boosted = 10_000 - goblin.current_hp
    assert boosted == pytest.approx(plain * 1.40, rel=0.01)
    goblin.current_hp = 10_000
    engine._apply_effect(state, "hero", "goblin_0", Effect(kind=EffectKind.DAMAGE, amount=100.0, damage_element=DamageElement.SHADOW))
    assert 10_000 - goblin.current_hp == pytest.approx(plain, rel=0.01)  # shadow untouched


def test_prestige_unlock_needs_two_evolved_races_and_the_ecos():
    meta = MetaProgressionState()
    meta.ecos = MEIO_CELESTIAL_COST
    assert meta.can_buy_race("meio_celestial") is False  # nothing evolved yet
    meta.unlock_race("elf")
    meta.evolved_races.update({"human", "elf", "orc"})  # orc evolved but not unlocked: doesn't count
    assert meta.evolved_race_count() == 2
    assert meta.can_buy_race("meio_celestial") is True
    meta.ecos = MEIO_CELESTIAL_COST - 1
    assert meta.buy_race("meio_celestial") is False
    meta.ecos = MEIO_CELESTIAL_COST
    assert meta.buy_race("meio_celestial") is True
    assert "meio_celestial" in meta.unlocked_races and meta.ecos == 0
    assert meta.buy_race("human") is False  # not a prestige race


def test_finishing_a_run_records_the_races_that_evolved(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    app = WyrdfallApp()
    client = app.start_new_run()
    hero = client.get_run().party[0]
    hero.race_evolution_id = "abencoado_pelo_destino"  # Humano evolved this run
    client.get_run().encounter_index = len(client.session.dungeon.encounters)
    client._last_summary = client.session.finalize_run()
    app.bank_run_reward()
    assert "human" in app.meta.evolved_races


def test_avatar_dividido_is_offered_only_to_a_meio_celestial_mistico():
    spec = SPECIALIZATION_DEFS["avatar_dividido"]
    assert spec.required_race == "meio_celestial" and spec.hybrid_branch
    celestial = _session().run.party[0]
    celestial.archetype_usage = {Archetype.MISTICO: 10.0}
    assert "avatar_dividido" in {s.id for s in qualifying_specializations(celestial)}
    human = _session(race_id="human").run.party[0]
    human.archetype_usage = {Archetype.MISTICO: 10.0}
    assert "avatar_dividido" not in {s.id for s in qualifying_specializations(human)}
    assert "mistico_avatar_dividido_path" in TALENT_TREES
    assert "luz_e_sombra" in build_ruleset().abilities


@pytest.mark.asyncio
async def test_the_guild_sells_the_prestige_race_once_the_gate_is_met(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from textual.widgets import Button

    from wyrdfall.app import WyrdfallApp

    app = WyrdfallApp()
    app.meta.ecos = MEIO_CELESTIAL_COST
    app.meta.unlock_race("elf")
    app.meta.evolved_races.update({"human", "elf"})
    async with app.run_test(size=(120, 400)) as pilot:
        await pilot.pause()
        await pilot.click("#meta")
        await pilot.pause(0.3)
        button = app.screen.query_one("#race_buy_meio_celestial", Button)
        assert button.disabled is False
        await pilot.click("#tab_racas")
        await pilot.pause()
        await pilot.click("#race_buy_meio_celestial")
        await pilot.pause(0.3)
        assert "meio_celestial" in app.meta.unlocked_races and app.meta.ecos == 0
        assert app.screen.query("#race_meio_celestial")  # now selectable
