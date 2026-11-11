import random

import pytest

from wyrdfall.domain.cards import CARD_DEFS, CARD_OFFER_SIZE, CARD_PRICES_BY_RARITY, roll_card_offer
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.events import EventDef, EventOptionDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.items import Rarity
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession, SessionError
from tests.test_session import play_encounter_to_completion


def make_session(encounters, seed=1, currency=100) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=0)
    dungeon = DungeonDef(id="test", name="Test", encounters=encounters)
    run = RunState(run_id="run1", seed=seed, dungeon_id=dungeon.id, party=[hero], currency_earned=currency)
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def goblin_fight(id: str = "e1") -> EncounterDef:
    return EncounterDef(id=id, name="Fight", enemy_ids=["goblin"])


# -- the pool --------------------------------------------------------------------


def test_every_card_is_well_formed_and_active_cards_resolve_in_the_ruleset():
    ruleset = build_ruleset()
    for card in CARD_DEFS.values():
        assert card.name and card.description
        assert card.is_active == (card.grants_ability is not None)
        if card.is_active:
            assert card.grants_ability in ruleset.abilities, card.id
        else:
            assert card.modifiers or card.triggered_effects, card.id
    assert {c.rarity for c in CARD_DEFS.values()} == {Rarity.COMUM, Rarity.RARO, Rarity.LENDARIO}


def test_offers_are_three_distinct_cards_and_elite_tier_reaches_lendaria():
    for seed in range(20):
        offer = roll_card_offer(False, random.Random(seed), CARD_DEFS)
        assert len(offer) == CARD_OFFER_SIZE and len(set(offer)) == CARD_OFFER_SIZE
    normal = [CARD_DEFS[c].rarity for s in range(200) for c in roll_card_offer(False, random.Random(s), CARD_DEFS)]
    elite = [CARD_DEFS[c].rarity for s in range(200) for c in roll_card_offer(True, random.Random(s), CARD_DEFS)]
    assert normal.count(Rarity.COMUM) > normal.count(Rarity.RARO) > 0
    assert Rarity.LENDARIO in elite
    assert elite.count(Rarity.LENDARIO) > normal.count(Rarity.LENDARIO)


# -- earning -------------------------------------------------------------------


def test_a_won_fight_offers_each_character_three_cards_and_a_new_win_replaces_an_old_offer():
    session = make_session([goblin_fight(), goblin_fight(id="e2")], seed=5)
    hero = session.run.party[0]
    hero.card_offer = ["stale"]

    play_encounter_to_completion(session)
    session.collect_victory_reward_and_advance()
    first = list(session.run.party[0].card_offer)
    assert len(first) == CARD_OFFER_SIZE and "stale" not in first

    play_encounter_to_completion(session)
    session.collect_victory_reward_and_advance()
    assert len(session.run.party[0].card_offer) == CARD_OFFER_SIZE
    # deterministic per seed + node + character, not per call
    assert first == roll_card_offer(False, RunState(run_id="r", seed=5, dungeon_id="d", party=[]).card_rng(0), CARD_DEFS)


def test_choosing_a_passive_card_applies_it_immediately_and_clears_the_offer():
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    attack_before = hero.computed_stats(session.ruleset).attack
    hero.card_offer = ["pedra_de_amolar", "botas_leves", "manto_puido"]

    session.choose_card("hero", "pedra_de_amolar")

    assert hero.cards == ["pedra_de_amolar"]
    assert hero.card_offer == []
    assert hero.computed_stats(session.ruleset).attack == attack_before + 2


def test_choosing_an_active_card_adds_its_ability_to_the_pool():
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    hero.card_offer = ["segundo_folego"]
    session.choose_card("hero", "segundo_folego")
    assert "card_second_wind" in hero.abilities
    assert hero.cards == ["segundo_folego"]


def test_choosing_a_card_not_in_the_offer_or_skipping_without_one_is_rejected():
    session = make_session([goblin_fight()])
    hero = session.run.party[0]
    hero.card_offer = ["botas_leves"]
    with pytest.raises(SessionError):
        session.choose_card("hero", "ira_antiga")
    with pytest.raises(SessionError):
        session.choose_card("nobody", "botas_leves")
    assert hero.cards == [] and hero.card_offer == ["botas_leves"]

    session.skip_card("hero")
    assert hero.card_offer == []
    with pytest.raises(SessionError):
        session.skip_card("hero")


def test_an_event_option_can_grant_a_card(monkeypatch):
    session = make_session([EncounterDef(id="ev", name="Evento", room_type="event")])
    hero = session.run.party[0]
    pool = {
        "only": EventDef(
            id="only", name="Only", text="...",
            options=[EventOptionDef(id="take", label="t", outcome_text="", card_id="amuleto_do_viajante")],
        )
    }
    monkeypatch.setattr("wyrdfall.engine.session.EVENT_DEFS", pool)
    max_hp_before = hero.computed_stats(session.ruleset).max_hp

    session.resolve_event("take")

    assert hero.cards == ["amuleto_do_viajante"]
    assert hero.computed_stats(session.ruleset).max_hp == max_hp_before + 5


def test_the_vendedor_sells_its_one_card_once_priced_by_rarity():
    session = make_session([EncounterDef(id="s", name="Loja", room_type="shop")], currency=100)
    hero = session.run.party[0]
    card_id = session.shop_card()
    price = CARD_PRICES_BY_RARITY[CARD_DEFS[card_id].rarity]

    session.buy_card("hero")
    assert hero.cards == [card_id]
    assert session.run.currency_earned == 100 - price
    with pytest.raises(SessionError):
        session.buy_card("hero")  # already sold

    session.reroll_shop()  # restocks the card too
    assert session.shop_state().card_sold is False

    broke = make_session([EncounterDef(id="s", name="Loja", room_type="shop")], currency=0)
    with pytest.raises(SessionError):
        broke.buy_card("hero")
    not_a_shop = make_session([goblin_fight()])
    with pytest.raises(SessionError):
        not_a_shop.shop_card()
