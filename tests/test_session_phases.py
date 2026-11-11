import pytest

from tests.test_session import make_session
from wyrdfall.domain.attributes import Atributo
from wyrdfall.engine.session import SessionError


@pytest.mark.parametrize("finished", [False, True])
@pytest.mark.parametrize("method,args", [
    ("allocate_talent", ("hero", "r1")),
    ("allocate_attribute", ("hero", Atributo.LUCK)),
    ("evolve_specialization", ("hero", "berserker")),
    ("equip_weapon", ("hero", "bow")),
    ("equip_ability", ("hero", "reckless_smash")),
    ("unequip_ability", ("hero", "strike")),
    ("socket_rune", ("hero", "rune_might", "strike")),
    ("unsocket_rune", ("hero", "rune_might")),
    ("absorb_rune", ("hero", "rune_might")),
    ("combine_runes", ("rune_might",)),
    ("equip_armor", ("hero", "head", "traveler_cap")),
    ("unequip_armor", ("hero", "head")),
    ("equip_accessory", ("hero", "lucky_charm")),
    ("unequip_accessory", ("hero", "lucky_charm")),
    ("socket_enchantment", ("hero", "traveler_cap", "ench_swiftness")),
    ("reroll_enchantment", ("hero", "traveler_cap", 0)),
])
def test_build_changes_are_rejected_during_combat_or_after_completion(finished, method, args):
    session = make_session(starting_talent_points=5)
    hero = session.run.party[0]
    hero.attribute_points_available = 3
    hero.abilities.append("reckless_smash")
    from wyrdfall.domain.inventory import add_equipment
    add_equipment(session.run, "traveler_cap")
    session.run.rune_inventory = ["rune_might", "rune_might"]
    session.run.currency_earned = 100
    if finished:
        session.run.is_complete = True
    else:
        session.start_current_encounter()
    before = session.run.model_dump()
    combat_before = session.combat_state.model_dump() if session.combat_state else None
    assert getattr(session, method)(*args) is False
    assert session.run.model_dump() == before
    assert (session.combat_state.model_dump() if session.combat_state else None) == combat_before


@pytest.mark.parametrize("method,args", [
    ("resolve_rest", ("meditar",)), ("resolve_event", ("unknown",)),
    ("choose_card", ("hero", "pedra_de_amolar")), ("skip_card", ("hero",)),
    ("buy_card", ("hero",)), ("buy_consumable", (0,)),
    ("reroll_shop", ()), ("leave_node", ()), ("decline_contracts", ()),
])
def test_room_and_reward_commands_cannot_mutate_an_active_combat(method, args):
    session = make_session()
    session.start_current_encounter()
    before = session.run.model_dump()
    with pytest.raises(SessionError):
        getattr(session, method)(*args)
    assert session.run.model_dump() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["local", "host"])
async def test_clients_cannot_manage_a_character_they_do_not_control(mode):
    from wyrdfall.net.game_client import LocalGameClient
    from wyrdfall.net.host_client import HostGameClient
    from wyrdfall.net.server import HostServer
    from wyrdfall.domain.content import build_ruleset
    session = make_session()
    friend = session.run.party[0].model_copy(deep=True, update={"id": "friend", "attribute_points_available": 2})
    session.run.party.append(friend)
    if mode == "host":
        server = HostServer(build_ruleset(), host_player_id="hero", host_player_name="Host")
        server.session = session
        client = HostGameClient(server)
    else:
        client = LocalGameClient(session, controlled_character_ids={"hero"})
    with pytest.raises(SessionError):
        await client.allocate_attribute("friend", Atributo.LUCK)
    assert friend.attribute_points_available == 2


@pytest.mark.asyncio
async def test_an_explicit_empty_control_set_does_not_grant_the_whole_party():
    from wyrdfall.net.game_client import LocalGameClient
    session = make_session()
    client = LocalGameClient(session, controlled_character_ids=set())
    assert client.local_character_ids() == set()
    with pytest.raises(SessionError):
        await client.allocate_talent("hero", "r1")
    assert session.run.party[0].build.talent_tree.points_available == 1
