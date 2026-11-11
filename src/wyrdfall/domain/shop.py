"""Vendedor (docs/design/14-estrutura-da-run.md §5): "compra Consumíveis
(poções) e rerolls com Fragmentos -- seleção rotativa, sorteada por
run". Sells Consumíveis today; Cartas join the stock whenever that
system exists. The stock is a pure function of the run seed, the node
index and how many rerolls were bought, so every client computes the
same shelf -- only the small mutable part (rerolls, what's been sold)
lives on RunState and travels with it."""

from __future__ import annotations

import random

from wyrdfall.domain.abilities import Ability
from wyrdfall.domain.cards import CardDef, sealed_card_ids
from wyrdfall.domain.consumables import ConsumableDef
from wyrdfall.domain.run import RunState, ShopState

SHOP_STOCK_SIZE = 3
SHOP_REROLL_COST = 5
# First-guess prices in Fragmentos, like every other balance number.
CONSUMABLE_PRICES: dict[str, int] = {
    "pocao_de_vida": 8,
    "pocao_de_resolucao": 8,
    "elixir": 12,
    "tomo_do_guerreiro": 20,
    "tomo_do_patrulheiro": 20,
    "tomo_do_mistico": 20,
    "tomo_do_guardiao": 20,
}


def shop_stock_for(run: RunState, state: ShopState, pool: dict[str, ConsumableDef]) -> list[str]:
    rng = random.Random(run.seed * 6_000_003 + state.node_index + state.rerolls * 7919)
    ordered = sorted(pool)
    return [rng.choice(ordered) for _ in range(SHOP_STOCK_SIZE)]


def shop_card_for(run: RunState, state: ShopState, pool: dict[str, CardDef], abilities: dict[str, Ability]) -> str:
    """The one Carta on the shelf (docs/design/14-estrutura-da-run.md §5's
    "Cartas específicas"), rerolled together with the consumables. Sealed
    cards (Selamentos) for any party member are out of the shared pool."""
    sealed = set()
    for character in run.party:
        sealed.update(sealed_card_ids(character, pool, abilities))
    rng = random.Random(run.seed * 8_000_003 + state.node_index + state.rerolls * 7919)
    candidates = sorted(cid for cid in pool if cid not in sealed) or sorted(pool)
    return rng.choice(candidates)
