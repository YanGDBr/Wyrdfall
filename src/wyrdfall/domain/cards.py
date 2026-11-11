"""Cartas (docs/design/10-sistemas-de-build.md §3.7): found during the
run -- offered 1-of-3 after every won fight, sometimes as an Evento
reward, sold by the Vendedor -- and granting "qualquer coisa": a flat
stat, a run-permanent passive (Modifier/TriggeredEffect, the same
primitive runes and items already produce), or a new active ability.
Passive cards apply immediately, forever within the run, and take no
slot; an active card's ability joins Character.abilities.

Active abilities join the known pool and compete for the normal active slots.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character
from wyrdfall.domain.items import Rarity
from wyrdfall.domain.models import DamageElement, Effect, EffectKind, Modifier, ModifierKind, Stat, TriggeredEffect, TriggerEvent

CARD_OFFER_SIZE = 3
# First-guess balance numbers, like every other rate in this corpus.
_RARITY_WEIGHTS: dict[Rarity, float] = {Rarity.COMUM: 0.70, Rarity.RARO: 0.28, Rarity.LENDARIO: 0.02}
_ELITE_RARITY_WEIGHTS: dict[Rarity, float] = {Rarity.COMUM: 0.45, Rarity.RARO: 0.45, Rarity.LENDARIO: 0.10}
CARD_PRICES_BY_RARITY: dict[Rarity, int] = {Rarity.COMUM: 15, Rarity.RARO: 25, Rarity.LENDARIO: 40}


class CardDef(BaseModel):
    id: str
    name: str
    description: str
    rarity: Rarity
    modifiers: list[Modifier] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    grants_ability: str | None = None
    damage_elements: set[DamageElement] = Field(default_factory=set)

    @property
    def is_active(self) -> bool:
        return self.grants_ability is not None


CARD_DEFS: dict[str, CardDef] = {
    # -- Comum: stat passives ------------------------------------------------
    "amuleto_do_viajante": CardDef(
        id="amuleto_do_viajante", name="Amuleto do Viajante", rarity=Rarity.COMUM,
        description="+5 de PV máximo.",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="card_amuleto_do_viajante")],
    ),
    "pedra_de_amolar": CardDef(
        id="pedra_de_amolar", name="Pedra de Amolar", rarity=Rarity.COMUM,
        description="+2 de Ataque.",
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="card_pedra_de_amolar")],
    ),
    "botas_leves": CardDef(
        id="botas_leves", name="Botas Leves", rarity=Rarity.COMUM,
        description="+1 de Velocidade.",
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="card_botas_leves")],
    ),
    "cantil_encantado": CardDef(
        id="cantil_encantado", name="Cantil Encantado", rarity=Rarity.COMUM,
        description="+0.5 de Resolução por turno.",
        modifiers=[
            Modifier(stat=Stat.RESOURCE_REGEN_PER_TURN, kind=ModifierKind.FLAT, value=0.5, source="card_cantil_encantado")
        ],
    ),
    "manto_puido": CardDef(
        id="manto_puido", name="Manto Puído", rarity=Rarity.COMUM,
        description="+5% de chance de Esquiva.",
        modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="card_manto_puido")],
    ),
    # -- Raro --------------------------------------------------------------------
    "anel_de_sangue": CardDef(
        id="anel_de_sangue", name="Anel de Sangue", rarity=Rarity.RARO,
        description="+8% de roubo de vida.",
        modifiers=[Modifier(stat=Stat.LIFESTEAL_PERCENT, kind=ModifierKind.FLAT, value=0.08, source="card_anel_de_sangue")],
    ),
    "escudo_runico": CardDef(
        id="escudo_runico", name="Escudo Rúnico", rarity=Rarity.RARO,
        description="+15% de chance de Bloqueio.",
        modifiers=[Modifier(stat=Stat.BLOCK_CHANCE, kind=ModifierKind.FLAT, value=0.15, source="card_escudo_runico")],
    ),
    "lamina_fantasma": CardDef(
        id="lamina_fantasma", name="Lâmina Fantasma", rarity=Rarity.RARO,
        description="+10% de chance de Crítico.",
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.10, source="card_lamina_fantasma")],
    ),
    "espinhos": CardDef(
        id="espinhos", name="Espinhos", rarity=Rarity.RARO,
        description="Quem te acerta sofre 2 de dano de volta.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TAKE_DAMAGE,
                effect=Effect(kind=EffectKind.DAMAGE, amount=2.0),
                applies_to="context",
                source="card_espinhos",
            )
        ],
    ),
    "segundo_folego": CardDef(
        id="segundo_folego", name="Segundo Fôlego", rarity=Rarity.RARO,
        description="Habilidade ativa: cura a si mesmo.",
        grants_ability="card_second_wind",
    ),
    # -- Lendário ----------------------------------------------------------------
    "ira_antiga": CardDef(
        id="ira_antiga", name="Ira Antiga", rarity=Rarity.LENDARIO,
        description="+25% de Ataque adicional.",
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.MORE, value=0.25, source="card_ira_antiga")],
    ),
    "pele_de_ferro": CardDef(
        id="pele_de_ferro", name="Pele de Ferro", rarity=Rarity.LENDARIO,
        description="+30% de Defesa adicional e +10 de PV máximo.",
        modifiers=[
            Modifier(stat=Stat.DEFENSE, kind=ModifierKind.MORE, value=0.30, source="card_pele_de_ferro"),
            Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=10, source="card_pele_de_ferro"),
        ],
    ),
    "chicote_de_chamas": CardDef(
        id="chicote_de_chamas", name="Chicote de Chamas", rarity=Rarity.LENDARIO,
        description="Habilidade ativa: um chicote de fogo num único alvo.",
        grants_ability="card_flame_lash",
    ),
    # 11-habilidades.md §14 -- the group-play triggers, as Cartas (cheap to
    # find, meaningful only with a party; they never fire solo)
    "vinganca": CardDef(
        id="vinganca", name="Vingança", rarity=Rarity.RARO,
        description="Quando um aliado cai, você ganha Fortalecido por 3 turnos.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_ALLY_DOWNED,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="empowered", duration=3),
                applies_to="self",
                source="card_vinganca",
            )
        ],
    ),
    "segunda_chance": CardDef(
        id="segunda_chance", name="Segunda Chance", rarity=Rarity.RARO,
        description="Ao ser revivido em combate, ganha um escudo de 8.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_REVIVE,
                effect=Effect(kind=EffectKind.APPLY_SHIELD, amount=8.0),
                applies_to="self",
                source="card_segunda_chance",
            )
        ],
    ),
    "sincronia": CardDef(
        id="sincronia", name="Sincronia", rarity=Rarity.COMUM,
        description="Cada Combo em Equipe que você fecha devolve 2 de recurso.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TEAM_COMBO,
                effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=2.0),
                applies_to="self",
                source="card_sincronia",
            )
        ],
    ),
    "quebra_postura": CardDef(
        id="quebra_postura", name="Quebra-Postura", rarity=Rarity.COMUM,
        description="Quebrar a Postura de um inimigo devolve 3 de recurso.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_POISE_BREAK,
                effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=3.0),
                applies_to="self",
                source="card_quebra_postura",
            )
        ],
    ),
    "ritmo": CardDef(
        id="ritmo", name="Ritmo", rarity=Rarity.RARO,
        description="Cada Combo por Sequência que você encadeia dá Acelerado por 1 turno.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_COMBO_EXTEND,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="acelerado", duration=1),
                applies_to="self",
                source="card_ritmo",
            )
        ],
    ),
    "fulgor_arcano": CardDef(
        id="fulgor_arcano", name="Fulgor Arcano", rarity=Rarity.LENDARIO,
        description="Habilidade ativa: energia arcana contra todos os inimigos.",
        grants_ability="card_arcane_flare",
    ),
}

from wyrdfall.domain.card_catalog import build_extra_cards

CARD_DEFS.update(build_extra_cards(CardDef))


def card_modifiers_for(character: Character) -> list[Modifier]:
    modifiers: list[Modifier] = []
    for card_id in character.cards:
        card = CARD_DEFS.get(card_id)
        if card is not None:
            modifiers.extend(card.modifiers)
    return modifiers


def card_triggered_effects_for(character: Character) -> list[TriggeredEffect]:
    effects: list[TriggeredEffect] = []
    for card_id in character.cards:
        card = CARD_DEFS.get(card_id)
        if card is not None:
            effects.extend(card.triggered_effects)
    return effects


def roll_card_offer(
    elite_tier: bool, rng: random.Random, pool: dict[str, CardDef], exclude: set[str] | None = None,
) -> list[str]:
    """CARD_OFFER_SIZE distinct card ids for one character after a won
    fight (docs/design/14-estrutura-da-run.md §5) -- an Elite or boss
    draws from the better rarity weights, where a Lendária is possible."""
    weights = _ELITE_RARITY_WEIGHTS if elite_tier else _RARITY_WEIGHTS
    rarities = list(weights)
    # Selamentos: sealed cards never appear as an offer (10-sistemas-de-build.md §7)
    pool = {cid: card for cid, card in pool.items() if cid not in (exclude or set())}
    offer: list[str] = []
    for _ in range(CARD_OFFER_SIZE):
        rarity = rng.choices(rarities, weights=[weights[r] for r in rarities], k=1)[0]
        candidates = sorted(cid for cid, card in pool.items() if card.rarity == rarity and cid not in offer)
        if not candidates:
            candidates = sorted(cid for cid in pool if cid not in offer)
        if not candidates:
            break
        offer.append(rng.choice(candidates))
    return offer


def card_damage_elements(card: CardDef, abilities: dict) -> set:
    """Every damage element a card touches -- through the ability it grants
    -- for the Selamentos offer filter (domain/sealing.py)."""
    elements = set(card.damage_elements)
    ability = abilities.get(card.grants_ability) if card.grants_ability else None
    if ability is not None:
        for effect in ability.effects:
            if effect.kind is EffectKind.DAMAGE:
                elements.add(effect.damage_element)
    from wyrdfall.domain.content.statuses import STATUS_DEFS
    for effect in ([t.effect for t in card.triggered_effects] + (ability.effects if ability else [])):
        if effect.kind is EffectKind.DAMAGE:
            elements.add(effect.damage_element)
        elif effect.kind is EffectKind.APPLY_STATUS:
            status = STATUS_DEFS.get(effect.status_id)
            if status and status.tick_effect and status.tick_effect.kind is EffectKind.DAMAGE:
                elements.add(status.tick_effect.damage_element)
    return elements


def sealed_card_ids(character, pool: dict[str, CardDef], abilities: dict) -> set[str]:
    from wyrdfall.domain.sealing import is_sealed_source

    out = set()
    for cid, card in pool.items():
        ability = abilities.get(card.grants_ability) if card.grants_ability else None
        weight = ability.archetype_weight if ability is not None else None
        if is_sealed_source(character, archetype_weight=weight, damage_elements=card_damage_elements(card, abilities)):
            out.add(cid)
    return out
