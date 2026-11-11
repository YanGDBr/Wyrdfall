import asyncio

import pytest
from textual import events
from textual.widgets import Button, Input, Static

from tests.test_net_integration import two_player_clients, wait_until
from tests.test_session import make_session
from tests.ui_helpers import click_button
from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.cards import CARD_DEFS, CARD_PRICES_BY_RARITY
from wyrdfall.domain.combat import Action
from wyrdfall.domain.models import ActiveStatus, Archetype
from wyrdfall.domain.shop import CONSUMABLE_PRICES
from wyrdfall.net.game_client import LocalGameClient
from wyrdfall.persistence.checkpoint import RunCheckpoint, load_checkpoint, save_checkpoint
from wyrdfall.ui.screens.combat import CombatScreen
from wyrdfall.ui.screens.equipment import EquipmentScreen
from wyrdfall.ui.screens.resume_run import ResumeRunScreen
from wyrdfall.ui.screens.shop import ShopScreen


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    return WyrdfallApp()


@pytest.mark.parametrize(
    ("item_id", "button_id"),
    [("traveler_tunic", "armor_equip_body__traveler_tunic"), ("ring_of_focus", "accessory_equip_ring_of_focus")],
)
async def test_equipment_with_duplicate_items_is_usable(app, item_id, button_id):
    session = make_session()
    from wyrdfall.domain.inventory import add_equipment
    pieces = [add_equipment(session.run, item_id), add_equipment(session.run, item_id)]
    button_ids = [button_id.removesuffix(item_id) + p.id for p in pieces]
    app.client = LocalGameClient(session)
    async with app.run_test(size=(160, 55)) as pilot:
        screen = EquipmentScreen()
        await app.push_screen(screen)
        for iid in button_ids:
            await wait_until(lambda: bool(screen.query(f"#{iid}")))
            assert len(screen.query(f"#{iid}")) == 1
    assert all(p.id in session.run.inventory for p in pieces)


def test_bleeding_kills_player_but_allies_can_keep_fighting():
    session = make_session()
    hero = session.run.party[0]
    ally = hero.model_copy(update={"id": "ally"})
    session.run.party.append(ally)
    hero.current_hp = 1
    hero.cheated_death_used = True
    hero.statuses = [ActiveStatus(status_id="bleeding", remaining_duration=3, stacks=3)]

    state = session.start_current_encounter()
    assert state.current_actor_id() == "ally"
    session.submit_action(Action(actor_id="ally", ability_id="guard"))

    assert not state.alive("hero")
    assert not state.is_over
    assert state.current_actor_id() == "goblin_0"


async def test_bleeding_kills_enemy_and_solo_ai_continues(app):
    session = make_session()
    state = session.start_current_encounter()
    enemy = state.combatants["goblin_0"]
    enemy.current_hp = 1
    enemy.statuses = [ActiveStatus(status_id="bleeding", remaining_duration=3)]
    session.submit_action(Action(actor_id="hero", ability_id="guard"))
    assert not enemy.is_alive
    assert state.current_actor_id() == "goblin_1"

    app.client = LocalGameClient(session)
    async with app.run_test(size=(120, 40)):
        await app.push_screen(CombatScreen())
        await wait_until(lambda: state.current_actor_id() == "hero")


async def test_bleeding_kills_enemy_and_coop_ai_continues(two_player_clients):
    server, host, guest = two_player_clients
    for hero in server.session.run.party:
        hero.base_stats.speed = 20 if hero.id == "host" else 1
    await host.start_current_encounter()
    await guest.start_current_encounter()
    await wait_until(lambda: guest.get_combat_state() is not None)
    state = server.session.combat_state
    enemy = state.combatants["goblin_0"]
    enemy.current_hp = 1
    enemy.statuses = [ActiveStatus(status_id="bleeding", remaining_duration=3)]

    await host.submit_action(Action(actor_id="host", ability_id="guard"))
    await wait_until(lambda: guest.get_combat_state().current_actor_id() == guest.player_id)

    assert not enemy.is_alive
    assert not state.is_over


def test_old_checkpoint_recovers_turn_stuck_on_dead_enemy():
    session = make_session()
    state = session.start_current_encounter()
    state.turn_index = state.turn_order.index("goblin_0")
    state.combatants["goblin_0"].current_hp = 0
    snapshot = RunCheckpoint.from_session(session, mode="solo")

    restored = RunCheckpoint.model_validate_json(snapshot.model_dump_json()).restore_session(session.ruleset)

    assert restored.combat_state.current_actor_id() == "goblin_1"
    restored.resolve_ai_turn()
    assert restored.combat_state.current_actor_id() == "hero"


async def test_repeated_target_shortcut_submits_one_attack(app):
    session = make_session()
    state = session.start_current_encounter()
    app.client = LocalGameClient(session)
    async with app.run_test(size=(160, 55)) as pilot:
        screen = CombatScreen()
        await app.push_screen(screen)
        await click_button(pilot, "#ability_strike")
        await wait_until(lambda: bool(screen.query("#target_goblin_0")))
        screen.post_message(events.Key("1", "1"))
        screen.post_message(events.Key("1", "1"))
        await wait_until(lambda: state.current_actor_id() != "hero")
        await pilot.pause()
        assert not screen.query("#target_goblin_0")
        assert sum("Hero usa" in line for line in state.log) == 1


async def test_shop_displays_filtered_card_and_charges_its_price(app):
    session = make_session(seed=1)
    session.run.party[0].sealed_archetypes = {Archetype.MISTICO}
    session.run.encounter_index = 3
    session.run.currency_earned = 25
    app.client = LocalGameClient(session)
    async with app.run_test(size=(160, 55)) as pilot:
        screen = ShopScreen()
        await app.push_screen(screen)
        await wait_until(lambda: bool(screen.query("#buy_card")))
        assert screen.query_one("#buy_card", Button).disabled
        card = CARD_DEFS["sino_estilhacos"]
        assert any(card.name in str(widget.content) for widget in screen.query("#shelf Static"))

        price = CARD_PRICES_BY_RARITY[card.rarity]
        session.run.currency_earned = price
        screen.refresh_shop()
        await wait_until(lambda: bool(screen.query("#buy_card")) and not screen.query_one("#buy_card", Button).disabled)
        await click_button(pilot, "#buy_card")
        assert session.run.party[0].cards == [card.id]
        assert session.run.currency_earned == 0


async def test_host_handles_purchase_after_guest_buys_same_item(app, two_player_clients, monkeypatch):
    server, host, guest = two_player_clients
    session = server.session
    session.run.seed = 1
    session.run.encounter_index = 3
    session.run.currency_earned = 100
    item_id = session.shop_stock()[0]
    await server._broadcast_state()
    await wait_until(lambda: guest.get_run().encounter_index == 3)
    app.client = host
    purchase_committed = asyncio.Event()
    release_update = asyncio.Event()
    send_original = server._send_broadcast

    async def delay_purchase_broadcast(message):
        if 0 in session.shop_state().sold:
            purchase_committed.set()
            await release_update.wait()
        await send_original(message)

    monkeypatch.setattr(server, "_send_broadcast", delay_purchase_broadcast)
    async with app.run_test(size=(160, 55)) as pilot:
        screen = ShopScreen()
        await app.push_screen(screen)
        await wait_until(lambda: bool(screen.query("#buy_0")))
        try:
            await guest.buy_consumable(0)
            await asyncio.wait_for(purchase_committed.wait(), 2)
            await click_button(pilot, "#buy_0")
            await wait_until(lambda: not screen.query("#buy_0"))
            assert app.screen is screen
            assert session.run.consumables == [item_id]
            assert session.run.currency_earned == 100 - CONSUMABLE_PRICES[item_id]
        finally:
            release_update.set()


async def test_click_on_old_shop_button_does_not_buy_from_new_stock(app):
    session = make_session(seed=1)
    session.run.encounter_index = 3
    session.run.currency_earned = 100
    app.client = LocalGameClient(session)
    async with app.run_test(size=(160, 55)) as pilot:
        screen = ShopScreen()
        await app.push_screen(screen)
        await wait_until(lambda: bool(screen.query("#buy_0")))
        # Apply the reroll before the button gets repainted.
        session.reroll_shop()
        before = session.run.model_copy(deep=True)
        await click_button(pilot, "#buy_0")
        assert session.run == before
        assert app.screen is screen


@pytest.mark.parametrize("port", ["-1", "65536"])
async def test_invalid_host_resume_port_keeps_checkpoint_and_shows_error(app, port):
    session = make_session()
    save_checkpoint(RunCheckpoint.from_session(session, mode="host", players={"hero": "Hero"}, port=8765))
    async with app.run_test(size=(120, 40)) as pilot:
        screen = ResumeRunScreen()
        await app.push_screen(screen)
        screen.query_one("#resume-address", Input).value = port
        await click_button(pilot, "#resume-confirm")
        assert app.screen is screen
        assert "65535" in str(screen.query_one("#resume-status", Static).content)
        assert app.host_server is None
        assert load_checkpoint().port == 8765
