import random

import pytest

from tests.test_cards import make_session, goblin_fight
from wyrdfall.domain.cards import CARD_DEFS, sealed_card_ids, roll_card_offer
from wyrdfall.domain.card_catalog import CARD_ABILITIES
from wyrdfall.domain.combat import Action
from wyrdfall.domain.content import build_ruleset
from wyrdfall.domain.models import DamageElement, EffectKind, TriggerEvent


def test_catalog_is_four_times_larger_and_covers_all_play_styles():
    assert len(CARD_DEFS) == 80
    assert len(CARD_ABILITIES) == 12
    triggers = {t.trigger for c in CARD_DEFS.values() for t in c.triggered_effects}
    assert {TriggerEvent.ON_BLOCK, TriggerEvent.ON_DODGE, TriggerEvent.ON_PARRY_SUCCESS,
            TriggerEvent.ON_TEAM_COMBO, TriggerEvent.ON_REVIVE, TriggerEvent.ON_COMBAT_START} <= triggers
    assert any(any(m.value < 0 for m in c.modifiers) for c in CARD_DEFS.values())


def test_every_effect_has_valid_status_and_active_cards_respect_slots():
    ruleset = build_ruleset()
    for card in CARD_DEFS.values():
        effects = [t.effect for t in card.triggered_effects]
        if card.grants_ability:
            effects += ruleset.abilities[card.grants_ability].effects
        for effect in effects:
            if effect.kind is EffectKind.APPLY_STATUS:
                assert effect.status_id in ruleset.statuses, card.id
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    hero.equipped_abilities = hero.abilities[:]
    for card in CARD_DEFS.values():
        if card.grants_ability:
            session._grant_card(hero, card.id)
    assert len(hero.equipped_abilities) == 4
    assert set(CARD_ABILITIES) <= set(hero.abilities)


def test_seals_filter_passive_elemental_procs_and_active_techniques():
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    hero.sealed_elements = {DamageElement.ARCANE, DamageElement.POISON, DamageElement.ICE}
    sealed = sealed_card_ids(hero, CARD_DEFS, session.ruleset.abilities)
    assert {"sino_estilhacos", "dente_vibora", "beijo_vibora", "agulha_glacial"} <= sealed
    assert "escama_morna" not in sealed
    for seed in range(50):
        assert not set(roll_card_offer(True, random.Random(seed), CARD_DEFS, sealed)) & sealed


def test_new_cards_actually_grant_opening_shields_and_tradeoff_stats():
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    before = hero.computed_stats(session.ruleset)
    session._grant_card(hero, "pedra_paciente")
    after = hero.computed_stats(session.ruleset)
    assert after.defense == before.defense + 2
    assert after.speed == pytest.approx(before.speed - 1)
    session._grant_card(hero, "primeiro_sopro")
    state = session.start_current_encounter()
    assert state.combatants[hero.id].shield_hp == 6


def test_actual_enemies_scale_with_humans_and_companions_do_not_count():
    from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES
    from wyrdfall.domain.factory import create_player_character
    from wyrdfall.domain.dungeon import difficulty_multiplier
    from wyrdfall.domain.companions import COMPANION_DEFS, build_companion
    values = []
    for count in range(1,5):
        session = make_session([goblin_fight()])
        for i in range(count - 1):
            session.run.party.append(create_player_character(f"guest{i}", "Guest", CLASS_DEFS["runeguard"],
                TALENT_TREES["runeguard_path"], ruleset=session.ruleset))
        session.run.companions = [build_companion(next(iter(COMPANION_DEFS.values())), session.run.party[0])]
        state = session.start_current_encounter()
        enemy = state.combatants[state.enemy_ids()[0]]
        values.append((enemy.base_stats.max_hp, enemy.base_stats.attack))
        assert difficulty_multiplier(0,count) == pytest.approx(1 + .35 * (count-1))
    for index, value in enumerate(values):
        assert value[0] / values[0][0] == pytest.approx(1 + index * .35)
        assert value[1] / values[0][1] == pytest.approx(1 + index * .35)


@pytest.mark.parametrize("ability_id", list(CARD_ABILITIES))
def test_every_new_active_card_can_be_equipped_and_used(ability_id):
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    card = next(c for c in CARD_DEFS.values() if c.grants_ability == ability_id)
    session._grant_card(hero, card.id)
    hero.equipped_abilities = [ability_id]
    hero.base_stats.speed = 99
    hero.base_stats.max_resource = hero.current_resource = 99
    ally = hero.model_copy(deep=True, update={"id": "ally", "name": "Ally"})
    ally.base_stats.speed = 1
    ally.current_hp = 0 if ability_id == "card_reacender" else 1
    session.run.party.append(ally)
    state = session.start_current_encounter()
    ability = session.ruleset.abilities[ability_id]
    assert ability in session.combat_engine.legal_abilities(state, hero.id)
    targets = session.combat_engine.legal_target_ids(state, hero.id, ability)
    session.submit_action(Action(actor_id=hero.id, ability_id=ability_id,
                                 target_ids=targets[:1] if ability.requires_target else []))
    assert state.combatants[hero.id].last_ability_id == ability_id
    if ability.uses_per_combat is not None:
        assert state.combatants[hero.id].uses_this_combat[ability_id] == 1
