"""The 4 permanent race trees added for Fada/Renascido/Construto/Licantropo
(docs/design/10-sistemas-de-build.md §6, 04-racas.md "Upgrade permanente")."""

import random

from wyrdfall.domain.combat import Action, CombatEngine
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.content.permanent_trees import PERMANENT_TREE_COST, PERMANENT_TREES
from wyrdfall.domain.enemies import instantiate_enemy
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Stat
from wyrdfall.domain.races import CONSTRUTO_SPEED_PENALTY, RACE_DEFS


def test_every_race_in_the_roster_has_a_permanent_tree():
    for race_id in RACE_DEFS:
        assert f"permanent_{race_id}" in PERMANENT_TREES, race_id
    assert len(PERMANENT_TREES) == 13  # 9 races + 4 archetypes


def test_each_upgrade_line_softens_its_races_documented_penalty():
    ruleset = build_ruleset()
    assert any(m.stat == Stat.HEALING_RECEIVED_PERCENT and m.value > 0 for m in PERMANENT_TREES["permanent_renascido"].modifiers_for({"permanent_renascido_1"}))
    assert any(m.stat == Stat.MAX_HP for m in PERMANENT_TREES["permanent_fada"].modifiers_for({"permanent_fada_1"}))
    speed_gain = sum(m.value for m in PERMANENT_TREES["permanent_construto"].modifiers_for({"permanent_construto_1", "permanent_construto_2"}) if m.stat == Stat.SPEED)
    assert speed_gain > 0 and CONSTRUTO_SPEED_PENALTY + speed_gain < 0  # softened, still slow
    assert PERMANENT_TREES["permanent_licantropo"].triggered_effects_for({"permanent_licantropo_1"})
    assert "instinto_selvagem" in ruleset.statuses


def test_a_construto_with_its_tree_moves_up_the_turn_order_but_still_behind_the_fast():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["guardiao"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    slow = create_player_character("slow", "Slow", class_def, tree, ruleset=ruleset, race_id="construto")
    boosted = create_player_character("fast", "Fast", class_def, tree, ruleset=ruleset, race_id="construto",
                                      permanent_modifiers=PERMANENT_TREES["permanent_construto"].modifiers_for({"permanent_construto_1", "permanent_construto_2"}))
    assert boosted.computed_stats(ruleset).speed > slow.computed_stats(ruleset).speed
    goblin = instantiate_enemy(__import__("wyrdfall.domain.content", fromlist=["ENEMY_DEFS"]).ENEMY_DEFS["goblin"], "goblin")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([slow, boosted], [goblin])
    assert state.turn_order.index("fast") < state.turn_order.index("slow")


def test_the_licantropo_tree_stacks_instinct_faster_through_the_permanent_trigger_channel(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    app = WyrdfallApp()
    app.meta.unlock_race("licantropo")
    app.meta.active_race_id = "licantropo"
    app.meta.ecos = PERMANENT_TREE_COST
    assert app.meta.allocate_permanent_node("permanent_licantropo", "permanent_licantropo_1") is True
    client = app.start_new_run()
    hero = client.get_run().party[0]
    assert any(t.source == "permanent_licantropo_1" for t in hero.permanent_triggered_effects)
    state = client.session.start_current_encounter()
    fighter = state.combatants["hero"]
    stacks = next((s.stacks for s in fighter.statuses if s.status_id == "instinto_selvagem"), 0)
    assert stacks == 2  # the race's own stack + the tree's, both at the first turn start
