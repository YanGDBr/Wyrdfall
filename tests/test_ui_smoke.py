from tests.ui_helpers import click_button
import pytest

from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.models import Archetype
from wyrdfall.domain.specializations import qualifying_specializations
from wyrdfall.ui.screens.bestiary import BestiaryScreen
from wyrdfall.ui.screens.combat import CombatScreen
from wyrdfall.ui.screens.dungeon import DungeonScreen
from wyrdfall.ui.screens.equipment import EquipmentScreen
from wyrdfall.ui.screens.evolution import EvolutionScreen
from wyrdfall.ui.screens.forge import ForgeScreen
from wyrdfall.ui.screens.main_menu import MainMenuScreen
from wyrdfall.ui.screens.meta_progression import MetaProgressionScreen
from wyrdfall.ui.screens.run_summary import RunSummaryScreen
from wyrdfall.ui.screens.skill_challenge import SkillChallengeScreen


@pytest.fixture
def app(tmp_path, monkeypatch):
    # keep tests from touching the developer's real save file
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    return WyrdfallApp()


@pytest.mark.asyncio
async def test_boots_to_main_menu(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)


@pytest.mark.asyncio
async def test_new_run_reaches_dungeon_screen(app):
    # explicit size: the archetype-select panel now has a Selamentos step
    # that can scroll "Começar Run" out of the default 80x24 test viewport.
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert app.client is not None
        assert app.client.get_run().party[0].name == "Herói"


@pytest.mark.asyncio
async def test_picking_a_non_default_portal_changes_the_runs_dungeon(app):
    from wyrdfall.domain.content import PORTAL_DEFS

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_gelo")
        await pilot.pause()

        assert isinstance(app.screen, DungeonScreen)
        run = app.client.get_run()
        assert run.dungeon_id == "portao_do_gelo"
        encounters = app.client.get_dungeon().encounters
        # Portão do Gelo starts at Área 3, not Área 1 like the default Portal
        assert encounters[0].area_id == "the_frozen_pinnacle"
        area_order = []
        for e in encounters:
            if not area_order or area_order[-1] != e.area_id:
                area_order.append(e.area_id)
        assert area_order == PORTAL_DEFS["portao_do_gelo"].path


@pytest.mark.asyncio
async def test_resting_at_a_descanso_node_heals_and_moves_the_run_on(app, monkeypatch):
    from wyrdfall.ui.screens.rest import RestScreen

    # the Sala Especial's type is drawn per run -- force this one to be a Descanso
    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "rest")
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        encounters = app.client.get_dungeon().encounters
        rest_index = next(i for i, e in enumerate(encounters) if e.room_type == "special")
        run = app.client.get_run()
        run.encounter_index = rest_index
        hero = run.party[0]
        hero.current_hp = 1.0
        app.screen.refresh_dungeon()
        await pilot.pause()
        assert str(app.screen.query_one("#enter").label) == "Descansar"

        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, RestScreen)

        await pilot.click("#acampar")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert app.client.get_run().encounter_index == rest_index + 1
        assert app.client.get_run().party[0].current_hp > 1.0


@pytest.mark.asyncio
async def test_choosing_an_event_option_applies_it_and_moves_the_run_on(app):
    from wyrdfall.domain.content import EVENT_DEFS
    from wyrdfall.domain.events import event_for_node
    from wyrdfall.ui.screens.event import EventScreen

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        encounters = app.client.get_dungeon().encounters
        event_index = next(i for i, e in enumerate(encounters) if e.room_type == "event")
        run = app.client.get_run()
        run.encounter_index = event_index
        app.screen.refresh_dungeon()
        await pilot.pause()
        assert str(app.screen.query_one("#enter").label) == "Investigar"

        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, EventScreen)

        event = event_for_node(run, EVENT_DEFS)
        option = event.options[-1]  # never has a cost
        await pilot.click(f"#option_{option.id}")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert app.client.get_run().encounter_index == event_index + 1
        assert app.client.get_run().party[0].alignment_score == option.alignment_shift


@pytest.mark.asyncio
async def test_drinking_a_potion_from_the_pouch_heals_the_hero(app):
    from wyrdfall.ui.screens.consumables import ConsumablesScreen

    async with app.run_test(size=(100, 40)) as pilot:
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
        run.consumables.append("pocao_de_vida")
        run.party[0].current_hp = 1.0
        app.screen.refresh_dungeon()
        await pilot.pause()
        assert str(app.screen.query_one("#consumables").label) == "Consumíveis (1/3)"

        await pilot.click("#consumables")
        await pilot.pause()
        assert isinstance(app.screen, ConsumablesScreen)

        await pilot.click("#use_0")
        await pilot.pause()
        assert app.client.get_run().consumables == []
        assert app.client.get_run().party[0].current_hp > 1.0

        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert str(app.screen.query_one("#consumables").label) == "Consumíveis (0/3)"


@pytest.mark.asyncio
async def test_choosing_a_card_from_a_pending_offer_applies_it(app):
    from wyrdfall.ui.screens.cards import CardsScreen

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        attack_before = hero.computed_stats(app.client.ruleset).attack
        # a won fight would set this (see test_cards.py) -- set it directly so
        # the UI path under test doesn't depend on winning a random combat
        hero.card_offer = ["pedra_de_amolar", "botas_leves", "manto_puido"]
        app.screen.refresh_dungeon()
        await pilot.pause()
        assert str(app.screen.query_one("#cards").label) == "Cartas (oferta!)"

        await pilot.click("#cards")
        await pilot.pause()
        assert isinstance(app.screen, CardsScreen)

        await pilot.click("#card_pedra_de_amolar")
        await pilot.pause()
        assert hero.cards == ["pedra_de_amolar"]
        assert hero.card_offer == []
        assert hero.computed_stats(app.client.ruleset).attack == attack_before + 2

        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert str(app.screen.query_one("#cards").label) == "Cartas"


@pytest.mark.asyncio
async def test_unequipping_and_re_equipping_an_ability_through_the_equipment_screen(app):
    from wyrdfall.ui.screens.equipment import EquipmentScreen

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

        hero = app.client.get_run().party[0]
        assert "strike" in hero.equipped_abilities
        await pilot.click("#equipment")
        await pilot.pause(0.2)
        assert isinstance(app.screen, EquipmentScreen)

        await pilot.click("#ability_unequip_strike")
        await pilot.pause(0.2)
        assert "strike" not in hero.equipped_abilities
        await pilot.click("#ability_equip_strike")
        await pilot.pause(0.2)
        assert "strike" in hero.equipped_abilities


@pytest.mark.asyncio
async def test_switching_stance_in_combat_marks_it_and_locks_further_switches_this_turn(app):
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        state = app.client.get_combat_state()
        assert state.current_actor_id() == "hero"

        await pilot.click("#stance_offensive")
        await pilot.pause()
        assert app.client.get_combat_state().combatants["hero"].current_stance == "offensive"
        assert app.client.get_combat_state().current_actor_id() == "hero"  # still the hero's turn
        assert app.screen.query_one("#stance_evasive").disabled  # one switch per turn
        assert str(app.screen.query_one("#stance_offensive").label).endswith("✓")  # marked as current


@pytest.mark.asyncio
async def test_buying_and_equipping_a_pact_in_the_guild_carries_into_the_next_run(app):
    from wyrdfall.persistence.store import RunSummary

    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        app.meta.ecos = 200
        # a recorded victory unlocks Ascensão (docs/design/14-estrutura-da-run.md §9)
        app.meta.record_run(RunSummary(run_id="w", class_id="runeguard", floor_reached=9, victory=True), ecos_earned=0)
        await pilot.click("#meta")
        await pilot.pause(0.2)
        assert isinstance(app.screen, MetaProgressionScreen)

        await pilot.click("#tab_pactos")
        await pilot.pause()
        await pilot.click("#pact_buy_inimigos_ferozes")
        await pilot.pause(0.2)
        assert "inimigos_ferozes" in app.meta.unlocked_pacts
        await pilot.click("#tab_pactos")
        await pilot.pause()
        await pilot.click("#pact_toggle_inimigos_ferozes")
        await pilot.pause(0.2)
        assert app.meta.equipped_pacts == ["inimigos_ferozes"]

        await pilot.click("#tab_geral")
        await pilot.pause()
        await pilot.click("#ascension_2")
        await pilot.pause(0.2)
        assert app.meta.ascension_level == 2

        await pilot.click("#back")
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
        assert run.active_pacts == ["inimigos_ferozes"] and run.ascension_level == 2
        assert run.wyrd_meter == 15.0
        assert "15/100" in app.screen.query_one("#run-status").text  # the Wyrd meter on the Run panel


@pytest.mark.asyncio
async def test_picking_a_non_default_archetype_changes_the_new_heros_class(app):
    # explicit size: the archetype-select panel now has a Selamentos step
    # (3 seal buttons) that can scroll "Começar Run" out of the default
    # 80x24 test viewport.
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_mistico")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        assert isinstance(app.screen, DungeonScreen)
        assert app.client.get_run().party[0].class_id == "mistico"


@pytest.mark.asyncio
async def test_entering_an_encounter_reaches_combat_screen_with_action_buttons(app):
    # explicit size: the dungeon panel now has enough buttons (Evoluir
    # Especialização added) to scroll "Entrar no Encontro" out of the
    # default 80x24 test viewport.
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        # the Runeguard is faster than the first encounter's goblins, so it should act first
        buttons = app.screen.query("#action-bar Button")
        assert len(buttons) > 0


@pytest.mark.asyncio
async def test_clicking_through_an_encounter_and_continue_reaches_dungeon_or_summary(app):
    """Regression test: clicking "Continue" after combat ends used to crash
    (the GameClient interface changed and combat.py wasn't updated to
    match). Drives real combat via the actual buttons, through at least one
    full "encounter -> Continue" cycle, whichever way it resolves."""
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)

        for _ in range(300):
            if not isinstance(app.screen, CombatScreen):
                break
            state = app.client.get_combat_state()
            if state.is_over:
                buttons = list(app.screen.query("#action-bar Button"))
                assert buttons and buttons[0].id == "combat_continue"
                await pilot.click(f"#{buttons[0].id}")
            else:
                buttons = list(app.screen.query("#action-bar Button"))
                if buttons:
                    await pilot.click(f"#{buttons[0].id}")
                else:
                    await pilot.pause(0.65)
            await pilot.pause()

        assert isinstance(app.screen, (DungeonScreen, RunSummaryScreen))


@pytest.mark.asyncio
async def test_allocating_a_talent_does_not_crash_and_updates_the_node_list(app):
    """Regression test: allocating a talent used to raise DuplicateIds
    because the node list was rebuilt without awaiting the removal of the
    old buttons before mounting the new ones."""
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        await pilot.click("#talents")
        await pilot.pause()

        # the tree's 13 nodes are split across "disponíveis" (buttons),
        # "alocados" and "bloqueados" (rows) -- only reachable nodes are buttons
        def node_count() -> int:
            return (
                len(list(app.screen.query("#talent-buttons Button")))
                + len(list(app.screen.query("#allocated-rows Static")))
                + len(list(app.screen.query("#locked-rows Static")))
            )

        buttons = list(app.screen.query("#talent-buttons Button"))
        assert len(buttons) == 3  # the three root nodes
        assert node_count() == 13 + 1  # + the "nothing allocated yet" placeholder
        allocatable = next(b for b in buttons if not b.disabled)
        node_id = allocatable.id.removeprefix("talent_")

        await pilot.click(f"#{allocatable.id}")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        assert node_id in hero.build.talent_tree.allocated
        assert node_count() == 13  # rebuilt, not duplicated

        # allocating a second node (rebuilding the list again) must not crash either
        second = next((b for b in app.screen.query("#talent-buttons Button") if not b.disabled), None)
        if second is not None:
            await pilot.click(f"#{second.id}")
            await pilot.pause()


@pytest.mark.asyncio
async def test_allocating_an_attribute_does_not_crash_and_updates_the_row_list(app):
    """Mirrors the talent-allocation regression test above: this screen
    rebuilds a dynamic button list too, so it must also await
    remove_children() before remounting (see AttributeScreen.refresh_attributes)."""
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        hero.attribute_points_available = 2

        await pilot.click("#attributes")
        await pilot.pause()

        buttons = list(app.screen.query("#attribute-rows Button"))
        assert len(buttons) == 6  # one per attribute
        assert all(not b.disabled for b in buttons)

        first_id = buttons[0].id
        attribute = Atributo(first_id.removeprefix("attr_"))
        await pilot.click(f"#{first_id}")
        await pilot.pause()

        assert hero.attribute_points[attribute] == 1
        assert hero.attribute_points_available == 1
        assert len(list(app.screen.query("#attribute-rows Button"))) == 6  # rebuilt, not duplicated

        # a second click (rebuilding the list again) must not crash either
        second_id = list(app.screen.query("#attribute-rows Button"))[0].id
        await pilot.pause(0.3)  # the same Button ignores a second press during its active flash
        await pilot.click(f"#{second_id}")
        await pilot.pause()

        assert hero.attribute_points_available == 0
        assert all(b.disabled for b in app.screen.query("#attribute-rows Button"))  # no points left


@pytest.mark.asyncio
async def test_parry_prompt_appears_for_a_can_parry_hero_and_resolves_via_decline(app, monkeypatch):
    # This test checks the prompt/decline path, not the timing difficulty.
    # Actual duration and hit boundaries are covered by test_parry_balance.
    monkeypatch.setattr(SkillChallengeScreen, "_tick", lambda self: None)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause(0.05)
        await pilot.click("#new_run")
        await pilot.pause(0.05)
        await pilot.click("#class_runeguard")
        await pilot.pause(0.05)
        await pilot.click("#confirm")
        await pilot.pause(0.05)
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause(0.05)

        hero = app.client.get_run().party[0]
        hero.can_parry = True

        await pilot.click("#enter")
        await pilot.pause(0.05)
        assert isinstance(app.screen, CombatScreen)

        # hero acts first (Runeguard is faster than the goblins) so it
        # becomes the goblin's turn next -- take whatever action is offered,
        # picking a target too if the ability needs one.
        buttons = list(app.screen.query("#action-bar Button"))
        assert buttons
        await pilot.click(f"#{buttons[0].id}")
        await pilot.pause(0.05)
        target_buttons = [b for b in app.screen.query("#action-bar Button") if (b.id or "").startswith("target_")]
        if target_buttons:
            await pilot.click(f"#{target_buttons[0].id}")
            await pilot.pause(0.05)

        # let the AI turn timer fire; the goblin's melee bite against a
        # can_parry hero should pause combat and open the minigame instead
        # of resolving immediately. From here on, use explicit short pause
        # durations rather than bare pilot.pause() -- the minigame's
        # set_interval keeps the message queue busy, so a bare pause (which
        # waits for the queue to go idle) would block until that timer
        # stops, i.e. until the auto-timeout beats us to "#decline".
        await pilot.pause(0.7)
        await pilot.pause(0.05)
        await pilot.pause(0.05)

        assert isinstance(app.screen, SkillChallengeScreen)
        assert app.client.get_combat_state().pending_parry is not None

        await pilot.click("#decline")
        await pilot.pause(0.05)
        await pilot.pause(0.05)

        assert isinstance(app.screen, CombatScreen)
        assert app.client.get_combat_state().pending_parry is None


@pytest.mark.asyncio
async def test_meta_progression_screen_opens_and_goes_back(app):
    # explicit size: the panel now has enough buttons/lines (Parry unlock,
    # races, conquistas) to scroll "Voltar" out of a smaller viewport.
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        await pilot.click("#meta")
        await pilot.pause(0.05)
        assert isinstance(app.screen, MetaProgressionScreen)
        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)


@pytest.mark.asyncio
async def test_toggling_fast_combat_persists_and_changes_the_ai_turn_delay(app):
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        await pilot.click("#meta")
        await pilot.pause(0.05)

        assert app.ai_turn_delay_seconds() == 0.6
        await pilot.click("#tab_opcoes")
        await pilot.pause()
        await pilot.click("#toggle_fast_combat")
        await pilot.pause()

        assert app.meta.fast_combat is True
        assert app.ai_turn_delay_seconds() == 0.15

        # the method itself reflects either state -- checked directly rather
        # than via a second click, since re-querying a button by id after its
        # own label just changed length is its own source of flakiness,
        # orthogonal to what this test is actually verifying.
        app.meta.fast_combat = False
        assert app.ai_turn_delay_seconds() == 0.6


@pytest.mark.asyncio
async def test_selecting_an_unlocked_race_in_the_guild_changes_the_next_run(app):
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        app.meta.unlock_race("dwarf")  # force-unlock, same as existing attribute/parry tests do
        await pilot.click("#meta")
        await pilot.pause(0.05)

        await pilot.click("#tab_racas")
        await pilot.pause()
        await pilot.click("#race_dwarf")
        await pilot.pause(0.05)
        assert app.meta.active_race_id == "dwarf"

        await pilot.click("#back")
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        assert app.client.get_run().party[0].race_id == "dwarf"


@pytest.mark.asyncio
async def test_allocating_a_permanent_tree_node_spends_ecos_and_applies_to_the_next_hero(app):
    async with app.run_test(size=(120, 400)) as pilot:
        await pilot.pause()
        app.meta.ecos = 100
        await pilot.click("#meta")
        await pilot.pause(0.2)

        await pilot.click("#tab_arvores")
        await pilot.pause()
        await pilot.click("#ptree_permanent_human__permanent_human_1")
        await pilot.pause(0.2)
        assert app.meta.ecos == 97
        assert "permanent_human_1" in app.meta.permanent_tree_allocated.get("permanent_human", set())

        await pilot.click("#back")
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        assert any(m.source == "permanent_human_1" for m in hero.permanent_modifiers)


@pytest.mark.asyncio
async def test_bestiary_screen_shows_a_discovered_enemy_and_hides_the_rest(app):
    # explicit size: the bestiary now lists enough enemies (Áreas 1-7)
    # that "Voltar" scrolls out of the default/smaller viewport, and a
    # pilot.click on a button below the visible viewport can silently
    # fail to register even though query_one still finds it (same
    # test-viewport scrolling artifact documented elsewhere in this
    # test suite -- not a real app bug). 300 rows like the other Guild
    # tests, since the Guild gained a Companheiro section in Fase 9.
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        app.meta.discover_enemy("goblin")  # force-discover, same pattern as force-unlocking a race
        await pilot.click("#meta")
        await pilot.pause(0.05)
        await pilot.click("#tab_missoes")
        await pilot.pause()
        await pilot.click("#bestiary")
        await pilot.pause(0.05)

        assert isinstance(app.screen, BestiaryScreen)
        body_text = app.screen.query_one("#bestiary-body").content
        assert "Goblin" in str(body_text)
        assert "???" in str(body_text)  # every undiscovered enemy still shows as unknown

        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(app.screen, MetaProgressionScreen)


@pytest.mark.asyncio
async def test_toggling_the_palette_applies_a_different_theme(app):
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        default_theme = app.theme
        await pilot.click("#meta")
        await pilot.pause(0.05)

        await pilot.click("#tab_opcoes")
        await pilot.pause()
        await pilot.click("#toggle_palette")
        await pilot.pause()

        assert app.meta.alt_palette is True
        assert app.theme != default_theme


@pytest.mark.asyncio
async def test_numeric_shortcut_activates_the_nth_action_button(app):
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)

        buttons_before = list(app.screen.query("#action-bar Button"))
        assert buttons_before  # Runeguard acts first, so ability buttons are showing
        first_id = buttons_before[0].id

        await pilot.press("1")
        await pilot.pause()

        # pressing "1" activated whatever the first button was -- if it
        # needed a target, we're now in target-select mode; if not, the
        # action already submitted and the bar shows something new either
        # way, proving the key routed through the same handler as a click.
        if (first_id or "").startswith("ability_"):
            ability_id = (first_id or "").removeprefix("ability_")
            ability = app.client.ruleset.abilities[ability_id]
            if ability.requires_target:
                assert any((b.id or "").startswith("target_") for b in app.screen.query("#action-bar Button"))


@pytest.mark.asyncio
async def test_evolving_a_qualifying_specialization_grants_the_new_branch(app):
    # explicit size: the dungeon panel scrolls "Evoluir Especialização"
    # out of the default 80x24 viewport, same as the "enter" test above.
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        # force-qualify for Berserker, same pattern as other tests forcing
        # eligibility directly rather than grinding usage through combat
        hero = app.client.get_run().party[0]
        hero.level = 5
        hero.archetype_usage = {Archetype.GUERREIRO: 100.0}

        # DungeonScreen only recomputes the "Evoluir" button's enabled state
        # on refresh_dungeon -- force one the same way the real on_update
        # notification would, since this direct mutation doesn't fire it.
        app.screen.refresh_dungeon()
        await pilot.pause()

        await pilot.click("#evolve")
        await pilot.pause()
        assert isinstance(app.screen, EvolutionScreen)

        # Options mount in a worker after the first screen refresh.
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.click("#spec_berserker")
        await pilot.pause()

        assert isinstance(app.screen, DungeonScreen)
        assert hero.specialization_id == "berserker"


@pytest.mark.asyncio
async def test_buying_and_picking_a_companion_in_the_guild_brings_it_into_combat(app):
    app.meta.ecos = 100
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        await pilot.click("#meta")
        await pilot.pause()
        assert isinstance(app.screen, MetaProgressionScreen)
        await pilot.click("#tab_companheiro")
        await pilot.pause()
        await pilot.click("#companion_buy_lobo_cinzento")
        await pilot.pause()
        assert "lobo_cinzento" in app.meta.unlocked_companions
        await pilot.click("#tab_companheiro")
        await pilot.pause()
        await pilot.click("#companion_pick_lobo_cinzento")
        await pilot.pause()
        assert app.meta.active_companion_id == "lobo_cinzento"
        await pilot.click("#back")
        await pilot.pause()

        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert "Companheiro de" in str(app.screen.query_one("#party-status").content)
        assert "Lobo Cinzento" in str(app.screen.query_one("#party-status").content)

        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        state = app.client.get_combat_state()
        assert "hero_companion" in state.party_ids()
        assert "(companheiro)" in str(app.screen.query_one("#party-panel").content)

        # let turns roll: the wolf's own turn is driven by the AI timer,
        # never by an action bar for the player
        for _ in range(6):
            await pilot.pause(0.3)
            state = app.client.get_combat_state()
            if state.is_over:
                break
            actor_id = state.current_actor_id()
            if actor_id == "hero":
                buttons = [b for b in app.screen.query("#action-bar Button") if (b.id or "").startswith("ability_")]
                if not buttons:  # action rows may still be rebuilding after the AI turn
                    continue
                await pilot.click(f"#{buttons[0].id}")
                await pilot.pause()
                targets = [b for b in app.screen.query("#action-bar Button") if (b.id or "").startswith("target_")]
                if targets:
                    await pilot.click(f"#{targets[0].id}")
                    await pilot.pause()
        assert any("Lobo Cinzento usa Mordida" in line for line in app.client.get_combat_state().log)


@pytest.mark.asyncio
async def test_contracts_screen_accepts_one_and_declines_the_rest(app):
    from wyrdfall.ui.screens.contracts import ContractsScreen

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        run = app.client.get_run()
        assert len(run.contract_offer) == 2
        assert "oferta" in str(app.screen.query_one("#contracts").label)

        await pilot.click("#contracts")
        await pilot.pause()
        assert isinstance(app.screen, ContractsScreen)
        first = run.contract_offer[0]
        await pilot.click(f"#accept_{first}")
        await pilot.pause()
        assert run.accepted_contracts == [first]
        await pilot.click("#decline_rest")
        await pilot.pause()
        assert run.contract_offer == []
        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert "oferta" not in str(app.screen.query_one("#contracts").label)


@pytest.mark.asyncio
async def test_forging_in_the_guild_adds_starting_gear_and_shows_mission_progress(app):
    from wyrdfall.domain.items import Rarity

    app.meta.ecos = 100
    app.meta.materials = {Rarity.COMUM: 2}
    async with app.run_test(size=(100, 400)) as pilot:
        await pilot.pause()
        await pilot.click("#meta")
        await pilot.pause()
        assert isinstance(app.screen, MetaProgressionScreen)
        assert "Comum: 2" in str(app.screen.query_one("#smith-status").content)
        assert app.screen.query_one("#craft_craft_guardian_helm").disabled  # no Raro material
        await pilot.click("#tab_ferreiro")
        await pilot.pause()
        await pilot.click("#craft_craft_traveler_cap")
        await pilot.pause()
        assert app.meta.starting_gear == ["traveler_cap"]
        assert "Caçador de Chefes" in str(app.screen.query_one("#mission-body").content)
        assert "[0/3]" in str(app.screen.query_one("#mission-body").content)


@pytest.mark.asyncio
async def test_sealing_elements_at_creation_reaches_the_hero_and_potions_show_in_combat(app):
    from wyrdfall.domain.models import DamageElement
    from wyrdfall.ui.screens.element_seal import ElementSealScreen

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#seal_elements")
        await pilot.pause()
        assert isinstance(app.screen, ElementSealScreen)
        await pilot.click("#element_fire")
        await pilot.pause()
        await pilot.click("#confirm_elements")
        await pilot.pause()
        assert "1 selado" in str(app.screen.query_one("#seal_elements").label)
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        hero = app.client.get_run().party[0]
        assert hero.sealed_elements == {DamageElement.FIRE}

        # a potion in the pouch is a combat action on the hero's turn
        app.client.get_run().consumables.append("pocao_de_vida")
        hero.base_stats.speed = 99
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        buttons = [b.id for b in app.screen.query("#action-bar Button")]
        assert any((b or "").startswith("consumable_") for b in buttons)
        hero_in_fight = app.client.get_combat_state().combatants["hero"]
        hero_in_fight.current_hp = 1.0
        await pilot.click("#consumable_0_pocao_de_vida")
        await pilot.pause()
        assert hero_in_fight.current_hp > 1.0
        assert app.client.get_run().consumables == []


@pytest.mark.asyncio
async def test_evolving_into_stage2_goes_through_the_same_screen(app):
    from wyrdfall.engine.session import EVOLUTION_STAGE2_LEVEL

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        # already a Berserker at level 10 -- Estágio 2 is what's under test
        hero = app.client.get_run().party[0]
        hero.archetype_usage = {Archetype.GUERREIRO: 100.0}
        hero.level = 9
        hero.specialization_id = "berserker"
        app.screen.refresh_dungeon()
        await pilot.pause()
        assert app.screen.query_one("#evolve").disabled  # Stage 2 waits for level 10

        hero.level = EVOLUTION_STAGE2_LEVEL
        app.screen.refresh_dungeon()
        await pilot.pause()
        await pilot.click("#evolve")
        await pilot.pause()
        assert isinstance(app.screen, EvolutionScreen)
        assert "Estágio 2" in str(app.screen.query_one("#evolution-title").content)
        assert not list(app.screen.query("#spec_berserker"))  # Stage-1 picks are gone

        await pilot.click("#spec_senhor_da_guerra")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert hero.stage2_specialization_id == "senhor_da_guerra"
        assert app.screen.query_one("#evolve").disabled  # nothing after Stage 2


@pytest.mark.asyncio
async def test_evolution_screen_shows_a_newly_reachable_attribute_led_specialization(app):
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_patrulheiro")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        hero.level = 5
        hero.archetype_usage = {Archetype.PATRULHEIRO: 100.0}
        hero.attribute_points = {Atributo.LUCK: 5}

        app.screen.refresh_dungeon()
        await pilot.pause()
        await pilot.click("#evolve")
        await pilot.pause()

        assert isinstance(app.screen, EvolutionScreen)
        assert list(app.screen.query("#spec_atirador"))


@pytest.mark.asyncio
async def test_evolution_screen_shows_variant_flavor_text_when_a_variant_applies(app):
    from textual.widgets import Collapsible
    from tests.ui_helpers import click_button

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        hero.level = 5
        hero.race_id = "dwarf"
        hero.archetype_usage = {Archetype.GUERREIRO: 100.0}

        app.screen.refresh_dungeon()
        await pilot.pause()
        await pilot.click("#evolve")
        await pilot.pause()

        assert isinstance(app.screen, EvolutionScreen)
        flavor_lines = [str(w.content) for w in app.screen.query(".spec-option Static")]
        assert any("Berserker Anão" in line for line in flavor_lines)
        app.screen.query_one("#variants_berserker", Collapsible).collapsed = False
        await click_button(pilot, "#variant_berserker__dwarf__base__base")
        assert isinstance(app.screen, DungeonScreen)
        assert hero.evolution_variants.race_id == "dwarf"


@pytest.mark.asyncio
async def test_equipping_a_weapon_through_the_ui_updates_the_character(app):
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

        hero = app.client.get_run().party[0]
        assert hero.equipped_weapon_type is None

        await pilot.click("#equipment")
        await pilot.pause(0.2)
        assert isinstance(app.screen, EquipmentScreen)

        await pilot.click("#tab_arma")
        await pilot.pause(0.2)
        piece = next(p for p in app.client.get_run().equipment_instances.values() if p.definition_id == "basic_bow")
        await click_button(pilot, f"#weapon_{piece.id}")
        await pilot.pause(0.3)
        assert hero.equipped_weapon_type == "bow"
        # Habilidades Exclusivas de Arma: equipping the bow put Disparo in
        # the pool (and a free slot), so it's a real button in combat
        assert "weapon_shot" in hero.equipped_abilities
        await pilot.click("#done")
        await pilot.pause()
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        if app.client.get_combat_state().current_actor_id() == "hero":
            assert list(app.screen.query("#ability_weapon_shot"))


@pytest.mark.asyncio
async def test_socketing_a_body_rune_changes_a_computed_stat(app):
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

        hero = app.client.get_run().party[0]
        app.client.get_run().rune_inventory = ["rune_might"]  # runes are drops now (08-itens-crafting.md)
        attack_before = hero.computed_stats(app.client.ruleset).attack

        await pilot.click("#equipment")
        await pilot.pause(0.2)
        await pilot.click("#tab_runas")
        await pilot.pause(0.2)
        await pilot.click("#body_add_rune_might")
        await pilot.pause(0.2)

        assert "rune_might" in hero.body_rune_slots
        attack_after = hero.computed_stats(app.client.ruleset).attack
        assert attack_after == pytest.approx(attack_before + 3.0)

        await pilot.click("#body_remove_rune_might")
        await pilot.pause(0.2)
        assert "rune_might" not in hero.body_rune_slots


@pytest.mark.asyncio
async def test_equipping_a_found_armor_piece_through_the_ui_updates_a_computed_stat(app):
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

        hero = app.client.get_run().party[0]
        # force state directly, same as every other unlock test this
        # session -- traveler_cap is a real EquipmentDef, this just skips
        # needing a real encounter drop to prove it in run.inventory.
        from wyrdfall.domain.inventory import add_equipment
        piece = add_equipment(app.client.get_run(), "traveler_cap")
        speed_before = hero.computed_stats(app.client.ruleset).speed

        await pilot.click("#equipment")
        await pilot.pause(0.2)
        assert isinstance(app.screen, EquipmentScreen)

        await pilot.click("#tab_armadura")
        await pilot.pause(0.2)
        await pilot.click(f"#armor_equip_head__{piece.id}")
        await pilot.pause(0.3)

        assert hero.equipped_armor["head"] == piece.id
        speed_after = hero.computed_stats(app.client.ruleset).speed
        assert speed_after == pytest.approx(speed_before + 1.0)


@pytest.mark.asyncio
async def test_rerolling_an_enchantment_through_the_forge_screen_changes_it(app, monkeypatch):
    # Forja de Campo is a Sala Especial outcome now (Fase 7), not a menu
    # button -- force the first special node to be a forge and enter it.
    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "forge")
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

        hero = app.client.get_run().party[0]
        from wyrdfall.domain.inventory import add_equipment
        piece = add_equipment(app.client.get_run(), "traveler_cap")

        await pilot.click("#equipment")
        await pilot.pause(0.2)
        await pilot.click("#tab_armadura")
        await pilot.pause(0.2)
        await pilot.click(f"#armor_equip_head__{piece.id}")
        await pilot.pause(0.2)
        await pilot.click("#tab_encantamentos")
        await pilot.pause(0.2)
        assert not any((b.id or "").startswith("enchant_socket_") for b in app.screen.query("Button"))
        await pilot.click("#done")
        await pilot.pause(0.2)

        # granted directly -- the earning side (Forja de Campo's Fragmentos/
        # material cost) is exercised at the domain level in test_items.py.
        run = app.client.get_run()
        run.currency_earned = 999
        from wyrdfall.domain.items import Rarity

        run.materials[Rarity.COMUM] = 5

        encounters = app.client.get_dungeon().encounters
        forge_index = next(i for i, e in enumerate(encounters) if e.room_type == "special")
        run.encounter_index = forge_index
        app.screen.refresh_dungeon()
        await pilot.pause(0.2)
        assert str(app.screen.query_one("#enter").label) == "Forja de Campo"

        await pilot.click("#enter")
        await pilot.pause(0.2)
        assert isinstance(app.screen, ForgeScreen)

        await click_button(pilot, f"#engrave_options_{piece.id} CollapsibleTitle")
        await pilot.pause(.2)
        app.screen.query_one(f"#engrave_{piece.id}__ench_swiftness").scroll_visible(immediate=True)
        await pilot.pause(.1)
        await click_button(pilot, f"#engrave_{piece.id}__ench_swiftness")
        await pilot.pause(0.3)
        assert piece.enchantments == ["ench_swiftness"]
        await click_button(pilot, f"#reroll_{piece.id}__0")
        await pilot.pause(0.3)
        assert piece.enchantments != ["ench_swiftness"]

        await pilot.click("#leave")
        await pilot.pause(0.2)
        assert isinstance(app.screen, DungeonScreen)
        assert run.encounter_index == forge_index + 1


@pytest.mark.asyncio
async def test_buying_from_the_vendedor_and_leaving_consumes_the_node(app, monkeypatch):
    from wyrdfall.domain.shop import CONSUMABLE_PRICES
    from wyrdfall.ui.screens.shop import ShopScreen

    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "shop")
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        encounters = app.client.get_dungeon().encounters
        shop_index = next(i for i, e in enumerate(encounters) if e.room_type == "special")
        run = app.client.get_run()
        run.encounter_index = shop_index
        run.currency_earned = 100
        app.screen.refresh_dungeon()
        await pilot.pause()
        assert str(app.screen.query_one("#enter").label) == "Visitar o Vendedor"

        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, ShopScreen)

        bought = app.client.shop_stock()[0]
        await pilot.click("#buy_0")
        await pilot.pause()
        assert run.consumables == [bought]
        assert run.currency_earned == 100 - CONSUMABLE_PRICES[bought]

        await pilot.click("#leave")
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        assert run.encounter_index == shop_index + 1


@pytest.mark.asyncio
async def test_sealing_an_archetype_at_run_start_carries_through_and_hides_offers(app):
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")  # Guerreiro -- the other 3 become sealable
        await pilot.pause()

        await pilot.click("#seal_mistico")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()

        hero = app.client.get_run().party[0]
        assert hero.sealed_archetypes == {Archetype.MISTICO}

        # force-qualify for Paladino (Guerreiro + Místico hybrid) -- sealing
        # Místico must hide it even though the usage numbers would pass
        hero.level = 5
        hero.archetype_usage = {Archetype.GUERREIRO: 60.0, Archetype.MISTICO: 30.0, Archetype.GUARDIAO: 10.0}
        offered_ids = {s.id for s in qualifying_specializations(hero)}
        assert "paladino" not in offered_ids
