import pytest

from wyrdfall.domain.pacts import PACT_DEFS, PACT_SLOT_COST, VANTAGEM_SLOTS_BASE, pact_modifiers_for
from wyrdfall.domain.wyrd import danger_multiplier, reward_multiplier, starting_wyrd
from wyrdfall.persistence.store import MetaProgressionState


def test_the_pool_has_both_kinds_and_every_risco_pays_and_costs_something():
    kinds = {p.kind for p in PACT_DEFS.values()}
    assert kinds == {"vantagem", "risco"}
    for pact in PACT_DEFS.values():
        assert pact.cost > 0 and pact.name and pact.description
        if pact.kind == "vantagem":
            assert pact.modifiers and pact.reward_bonus == 0 and pact.enemy_power_bonus == 0 and pact.wyrd_gain == 0
        else:
            assert pact.reward_bonus > 0 and pact.wyrd_gain > 0
            assert pact.modifiers or pact.enemy_power_bonus > 0  # it must actually hurt


def test_buying_is_once_and_costs_ecos():
    meta = MetaProgressionState(ecos=100)
    cost = PACT_DEFS["fio_afiado"].cost
    assert meta.buy_pact("fio_afiado") is True
    assert meta.ecos == 100 - cost
    assert meta.buy_pact("fio_afiado") is False  # already owned
    assert meta.buy_pact("nao_existe") is False
    broke = MetaProgressionState(ecos=0)
    assert broke.buy_pact("fio_afiado") is False


def test_vantagens_are_capped_by_slots_and_riscos_are_not():
    meta = MetaProgressionState(ecos=1000)
    for pact_id in PACT_DEFS:
        meta.buy_pact(pact_id)
    vantagens = [p.id for p in PACT_DEFS.values() if p.kind == "vantagem"]
    riscos = [p.id for p in PACT_DEFS.values() if p.kind == "risco"]
    assert meta.vantagem_slots == VANTAGEM_SLOTS_BASE

    assert all(meta.toggle_pact(pid) for pid in vantagens[:VANTAGEM_SLOTS_BASE])
    assert meta.toggle_pact(vantagens[VANTAGEM_SLOTS_BASE]) is False  # slots full
    assert all(meta.toggle_pact(pid) for pid in riscos)  # no cap on risk

    ecos_before = meta.ecos
    assert meta.buy_vantagem_slot() is True
    assert meta.ecos == ecos_before - PACT_SLOT_COST
    assert meta.toggle_pact(vantagens[VANTAGEM_SLOTS_BASE]) is True

    assert meta.toggle_pact(vantagens[0]) is True  # unequip
    assert vantagens[0] not in meta.equipped_pacts
    unowned = MetaProgressionState()
    assert unowned.toggle_pact("fio_afiado") is False


def test_equipped_pacts_resolve_to_modifiers_and_risk_numbers():
    modifiers = pact_modifiers_for(["fio_afiado", "sangue_fino", "nao_existe"])
    assert {m.source for m in modifiers} == {"pact_fio_afiado", "pact_sangue_fino"}
    assert starting_wyrd(["fio_afiado"]) == 0.0
    assert starting_wyrd(["sangue_fino", "inimigos_ferozes"]) == 30.0
    assert starting_wyrd([p.id for p in PACT_DEFS.values() if p.kind == "risco"] * 3) == 100.0  # clamped


def test_a_run_started_with_pacts_carries_them_onto_the_hero_and_the_multipliers(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    app = WyrdfallApp()
    app.meta.ecos = 1000
    app.meta.buy_pact("fio_afiado")
    app.meta.buy_pact("inimigos_ferozes")
    app.meta.toggle_pact("fio_afiado")
    app.meta.toggle_pact("inimigos_ferozes")

    baseline_attack = WyrdfallApp().build_hero("h", "H").computed_stats(app.ruleset).attack
    client = app.start_new_run()
    run = client.get_run()
    hero = run.party[0]

    assert run.active_pacts == ["fio_afiado", "inimigos_ferozes"]
    assert hero.computed_stats(app.ruleset).attack == baseline_attack + 2
    assert run.wyrd_meter == pytest.approx(15.0)
    assert danger_multiplier(run) > 1.0 and reward_multiplier(run) > 1.0
