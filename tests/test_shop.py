import pytest

from wyrdfall.domain.consumables import CONSUMABLE_SLOTS
from wyrdfall.domain.content import CLASS_DEFS, CONSUMABLE_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.run import RunState, ShopState
from wyrdfall.domain.shop import CONSUMABLE_PRICES, SHOP_REROLL_COST, SHOP_STOCK_SIZE, shop_stock_for
from wyrdfall.engine.session import GameSession, SessionError


def make_shop_session(room: str = "shop", seed=1, currency=100, consumables=()) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=0)
    dungeon = DungeonDef(
        id="test", name="Test",
        encounters=[
            EncounterDef(id="s1", name="Sala", room_type=room),
            EncounterDef(id="e1", name="Fight", enemy_ids=["goblin"]),
        ],
    )
    run = RunState(
        run_id="run1", seed=seed, dungeon_id=dungeon.id, party=[hero],
        currency_earned=currency, consumables=list(consumables),
    )
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def test_stock_is_deterministic_per_seed_node_and_reroll_count():
    run = RunState(run_id="r", seed=3, dungeon_id="d", party=[], encounter_index=4)
    first = shop_stock_for(run, ShopState(node_index=4), CONSUMABLE_DEFS)
    assert len(first) == SHOP_STOCK_SIZE and set(first) <= set(CONSUMABLE_DEFS)
    assert shop_stock_for(run, ShopState(node_index=4), CONSUMABLE_DEFS) == first
    rerolled = {tuple(shop_stock_for(run, ShopState(node_index=4, rerolls=n), CONSUMABLE_DEFS)) for n in range(12)}
    assert len(rerolled) > 1


def test_buying_pays_fills_the_pouch_and_marks_the_slot_sold():
    session = make_shop_session()
    stock = session.shop_stock()
    price = CONSUMABLE_PRICES[stock[1]]

    session.buy_consumable(1)

    assert session.run.consumables == [stock[1]]
    assert session.run.currency_earned == 100 - price
    assert session.shop_state().sold == [1]
    with pytest.raises(SessionError):
        session.buy_consumable(1)  # already sold


def test_buying_is_rejected_when_unaffordable_or_the_pouch_is_full_or_off_a_shop():
    poor = make_shop_session(currency=0)
    with pytest.raises(SessionError):
        poor.buy_consumable(0)
    assert poor.run.consumables == []

    full = make_shop_session(consumables=["elixir"] * CONSUMABLE_SLOTS)
    with pytest.raises(SessionError):
        full.buy_consumable(0)

    not_a_shop = make_shop_session(room="rest")
    with pytest.raises(SessionError):
        not_a_shop.shop_stock()
    with pytest.raises(SessionError):
        not_a_shop.buy_consumable(0)


def test_rerolling_pays_redraws_and_clears_sold_slots():
    session = make_shop_session()
    before = session.shop_stock()
    session.buy_consumable(0)

    session.reroll_shop()

    state = session.shop_state()
    assert state.rerolls == 1 and state.sold == []
    assert session.run.currency_earned == 100 - CONSUMABLE_PRICES[before[0]] - SHOP_REROLL_COST
    session.buy_consumable(0)  # slot 0 is purchasable again

    broke = make_shop_session(currency=SHOP_REROLL_COST - 1)
    with pytest.raises(SessionError):
        broke.reroll_shop()


def test_leave_node_advances_clears_shop_state_and_only_works_on_shop_or_forge():
    session = make_shop_session()
    session.buy_consumable(0)
    assert session.run.shop is not None

    session.leave_node()
    assert session.run.encounter_index == 1
    assert session.run.shop is None
    with pytest.raises(SessionError):
        session.leave_node()  # now on the goblin fight

    forge = make_shop_session(room="forge")
    forge.leave_node()
    assert forge.run.encounter_index == 1

    rest = make_shop_session(room="rest")
    with pytest.raises(SessionError):
        rest.leave_node()


def test_shop_state_resets_when_the_run_reaches_a_different_node():
    session = make_shop_session()
    session.buy_consumable(0)
    # simulate a stale ShopState from an earlier node
    session.run.shop = ShopState(node_index=99, rerolls=3, sold=[0, 1])
    assert session.shop_state().node_index == 0
    assert session.shop_state().sold == [] and session.shop_state().rerolls == 0
