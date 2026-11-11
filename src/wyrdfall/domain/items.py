"""Equipment: armadura, acessórios and Encantamentos (docs/design/
10-sistemas-de-build.md §3.3, §3.5-3.6). Armor uses 3 fixed slots
(Cabeça/Corpo/Pernas, never expand) with a 2-piece/3-piece set bonus;
accessories use 3 slots with no set bonus. An Encantamento is, like a
Runa, "just another producer of Modifier/TriggeredEffect" -- the only
difference is which pool it's socketed into (an equipped item's own
slots, capped by that item's rarity) rather than a character-wide pool.

No drop/acquisition pipeline existed before Fase 6 (domain/loot.py now
provides one) -- this catalog is a small first pass, not the final
roster; more pieces/enchantments are ordinary content work for later.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Modifier, ModifierKind, Stat, TriggeredEffect, TriggerEvent, Effect, EffectKind, DamageElement


class Rarity(str, Enum):
    COMUM = "comum"
    RARO = "raro"
    LENDARIO = "lendario"


ENCHANTMENT_SLOTS_BY_RARITY: dict[Rarity, int] = {
    Rarity.COMUM: 1,
    Rarity.RARO: 2,
    Rarity.LENDARIO: 3,
}

# 3 fixed armor slots (head/body/legs, never expands) is implicit in
# EquipmentDef.slot's own Literal; accessories have no such type-level
# cap so it's spelled out here, mirroring runes.py's BODY_RUNE_SLOTS.
ACCESSORY_SLOTS = 3


class EquipmentDef(BaseModel):
    id: str
    name: str
    description: str = ""
    slot: str  # "head" | "body" | "legs" | "accessory"
    rarity: Rarity
    set_id: str | None = None
    modifiers: list[Modifier] = Field(default_factory=list)
    weapon_type_id: str | None = None
    required_element: DamageElement | None = None
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    random_drop: bool = True


class ArmorSetDef(BaseModel):
    id: str
    name: str
    description: str = ""
    two_piece_modifiers: list[Modifier] = Field(default_factory=list)
    three_piece_modifiers: list[Modifier] = Field(default_factory=list)
    three_piece_effects: list[TriggeredEffect] = Field(default_factory=list)


class EnchantmentDef(BaseModel):
    id: str
    name: str
    description: str
    required_element: DamageElement | None = None
    modifiers: list[Modifier] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)


EQUIPMENT_DEFS: dict[str, EquipmentDef] = {
    # -- Conjunto do Guardião (3 peças, RARO, prova o bônus de conjunto) --
    "guardian_helm": EquipmentDef(
        id="guardian_helm", name="Elmo do Guardião", slot="head", rarity=Rarity.RARO, set_id="guardian",
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="guardian_helm")],
    ),
    "guardian_chest": EquipmentDef(
        id="guardian_chest", name="Peitoral do Guardião", slot="body", rarity=Rarity.RARO, set_id="guardian",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=8, source="guardian_chest")],
    ),
    "guardian_greaves": EquipmentDef(
        id="guardian_greaves", name="Grevas do Guardião", slot="legs", rarity=Rarity.RARO, set_id="guardian",
        modifiers=[Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.05, source="guardian_greaves")],
    ),
    # -- Peças avulsas (COMUM, sem conjunto) --
    "traveler_cap": EquipmentDef(
        id="traveler_cap", name="Gorro do Viajante", slot="head", rarity=Rarity.COMUM,
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="traveler_cap")],
    ),
    "traveler_tunic": EquipmentDef(
        id="traveler_tunic", name="Túnica do Viajante", slot="body", rarity=Rarity.COMUM,
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=4, source="traveler_tunic")],
    ),
    "traveler_boots": EquipmentDef(
        id="traveler_boots", name="Botas do Viajante", slot="legs", rarity=Rarity.COMUM,
        modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.02, source="traveler_boots")],
    ),
    # -- Acessórios (sem conjunto, por design) --
    "ring_of_focus": EquipmentDef(
        id="ring_of_focus", name="Anel do Foco", slot="accessory", rarity=Rarity.COMUM,
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.03, source="ring_of_focus")],
    ),
    "amulet_of_vigor": EquipmentDef(
        id="amulet_of_vigor", name="Amuleto do Vigor", slot="accessory", rarity=Rarity.RARO,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=3, source="amulet_of_vigor")],
    ),
    "crown_of_ages": EquipmentDef(
        id="crown_of_ages", name="Coroa das Eras", slot="accessory", rarity=Rarity.LENDARIO,
        modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=4, source="crown_of_ages")],
    ),
}

ARMOR_SET_DEFS: dict[str, ArmorSetDef] = {
    "guardian": ArmorSetDef(
        id="guardian", name="Conjunto do Guardião",
        description="2 peças: +10% Defesa. 3 peças: mais +15% Defesa e +10% resistência a status.",
        two_piece_modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.PERCENT, value=0.10, source="guardian_set_2pc")],
        three_piece_modifiers=[
            Modifier(stat=Stat.DEFENSE, kind=ModifierKind.PERCENT, value=0.15, source="guardian_set_3pc"),
            Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.10, source="guardian_set_3pc"),
        ],
    ),
}

ENCHANTMENT_DEFS: dict[str, EnchantmentDef] = {
    "ench_power": EnchantmentDef(
        id="ench_power", name="Encantamento do Poder", description="+2 de Ataque.",
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="ench_power")],
    ),
    "ench_ward": EnchantmentDef(
        id="ench_ward", name="Encantamento da Guarda", description="+2 de Defesa.",
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="ench_ward")],
    ),
    "ench_vitality": EnchantmentDef(
        id="ench_vitality", name="Encantamento da Vitalidade", description="+6 de PV máximo.",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=6, source="ench_vitality")],
    ),
    "ench_swiftness": EnchantmentDef(
        id="ench_swiftness", name="Encantamento da Presteza", description="+1 de Velocidade.",
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="ench_swiftness")],
    ),
    "ench_precision": EnchantmentDef(
        id="ench_precision", name="Encantamento da Precisão", description="+4% de chance de Crítico.",
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.04, source="ench_precision")],
    ),
    "ench_resolve": EnchantmentDef(
        id="ench_resolve", name="Encantamento da Resolução", description="+2 de Resolução máxima.",
        modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=2, source="ench_resolve")],
    ),
}


# Weapons retain their type's attribute scaling and ability kit. Every player
# receives a personal basic arsenal; found versions have their own affixes.
from wyrdfall.domain.weapons import WEAPON_TYPE_DEFS

for _weapon in WEAPON_TYPE_DEFS.values():
    EQUIPMENT_DEFS[f"basic_{_weapon.id}"] = EquipmentDef(
        id=f"basic_{_weapon.id}", name=f"{_weapon.name} de treino", slot="weapon",
        rarity=Rarity.COMUM, weapon_type_id=_weapon.id, random_drop=False,
    )
    EQUIPMENT_DEFS[f"forged_{_weapon.id}"] = EquipmentDef(
        id=f"forged_{_weapon.id}", name=f"{_weapon.name} do Peregrino", slot="weapon",
        rarity=Rarity.RARO, weapon_type_id=_weapon.id,
        modifiers=[Modifier(stat=Stat.WEAPON_DAMAGE_PERCENT, kind=ModifierKind.FLAT,
                            value=0.06, source=f"forged_{_weapon.id}")],
    )

for _sid, _name, _stats in (
    ("windrunner", "Passo do Vento", [(Stat.CRIT_CHANCE, .02), (Stat.MAX_HP, 4), (Stat.SPEED, 1)]),
    ("weaver", "Tecelão de Ecos", [(Stat.MAX_RESOURCE, 2), (Stat.MAX_HP, 4), (Stat.HEALING_DONE_PERCENT, .08)]),
):
    for (_slot, _label), (_stat, _value) in zip(
        (("head", "Capuz"), ("body", "Manto"), ("legs", "Botas")), _stats,
    ):
        _iid = f"{_sid}_{_slot}"
        EQUIPMENT_DEFS[_iid] = EquipmentDef(id=_iid, name=f"{_label} do {_name}", slot=_slot,
            rarity=Rarity.RARO, set_id=_sid,
            modifiers=[Modifier(stat=_stat, kind=ModifierKind.FLAT, value=_value, source=_iid)])

ARMOR_SET_DEFS.update({
    "windrunner": ArmorSetDef(id="windrunner", name="Passo do Vento",
        description="2 peças: +4% esquiva. 3 peças: críticos restauram 1 recurso.",
        two_piece_modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=.04, source="windrunner_2")],
        three_piece_effects=[TriggeredEffect(trigger=TriggerEvent.ON_CRIT,
            effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1), source="windrunner_3")]),
    "weaver": ArmorSetDef(id="weaver", name="Tecelão de Ecos",
        description="2 peças: +12% cura causada. 3 peças: combos de equipe dão 5 de escudo a quem os ativa.",
        two_piece_modifiers=[Modifier(stat=Stat.HEALING_DONE_PERCENT, kind=ModifierKind.FLAT, value=.12, source="weaver_2")],
        three_piece_effects=[TriggeredEffect(trigger=TriggerEvent.ON_TEAM_COMBO,
            effect=Effect(kind=EffectKind.APPLY_SHIELD, amount=5), source="weaver_3")]),
})

EQUIPMENT_DEFS.update({
    "hollow_aegis": EquipmentDef(id="hollow_aegis", name="Égide do Trono Oco", slot="weapon",
        description="Começa cada combate com 6 de escudo.",
        rarity=Rarity.RARO, weapon_type_id="shield", random_drop=False,
        triggered_effects=[TriggeredEffect(trigger=TriggerEvent.ON_COMBAT_START,
            effect=Effect(kind=EffectKind.APPLY_SHIELD, amount=6), source="hollow_aegis")]),
    "ashkarion_staff": EquipmentDef(id="ashkarion_staff", name="Brasa de Ashkarion", slot="weapon",
        description="+20% dano de Fogo. Incompatível com Fogo selado.",
        rarity=Rarity.RARO, weapon_type_id="staff", required_element=DamageElement.FIRE, random_drop=False,
        modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=.20, source="ashkarion_staff", tags=["element:fire"])]),
    "widow_bow": EquipmentDef(id="widow_bow", name="Arco da Viúva Invernal", slot="weapon",
        description="+6% crítico e +15% dano de Gelo. Incompatível com Gelo selado.",
        rarity=Rarity.RARO, weapon_type_id="bow", required_element=DamageElement.ICE, random_drop=False,
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=.06, source="widow_bow"),
                   Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=.15, source="widow_bow", tags=["element:ice"])]),
})

# Elemental engravings provide an acquisition rule for the thematic boss drops.
for _element, _name in (
    (DamageElement.FIRE, "Fogo"), (DamageElement.ICE, "Gelo"),
    (DamageElement.LIGHTNING, "Raio"), (DamageElement.WATER, "Água"),
    (DamageElement.EARTH, "Terra"), (DamageElement.AIR, "Ar"),
    (DamageElement.POISON, "Veneno"), (DamageElement.HOLY, "Sagrado"),
    (DamageElement.SHADOW, "Sombrio"), (DamageElement.ARCANE, "Arcano"),
):
    _eid = f"ench_{_element.value}"
    ENCHANTMENT_DEFS[_eid] = EnchantmentDef(id=_eid, name=f"Encantamento de {_name}",
        description=f"+10% dano de {_name}.", required_element=_element,
        modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT,
                            value=.10, source=_eid, tags=[f"element:{_element.value}"])])

# The three reference bosses above establish the format. The remaining tables
# use the same modifiers/triggers, without changing their P7 combat mechanics.
for _iid, _name, _slot, _element, _stat, _value, _rarity in (
    ("storm_lens", "Lente de Voltharion", "accessory", DamageElement.LIGHTNING, Stat.CRIT_CHANCE, .04, Rarity.RARO),
    ("tidal_mantle", "Manto das Profundezas", "body", DamageElement.WATER, Stat.HEALING_DONE_PERCENT, .15, Rarity.RARO),
    ("mountain_heart", "Coração da Montanha", "accessory", DamageElement.EARTH, Stat.DEFENSE, 4, Rarity.LENDARIO),
    ("last_gale", "Passos da Última Rajada", "legs", DamageElement.AIR, Stat.DODGE_CHANCE, .05, Rarity.RARO),
    ("rot_diadem", "Diadema da Mãe Pútrida", "head", DamageElement.POISON, Stat.STATUS_RESIST, .10, Rarity.RARO),
    ("fallen_halo", "Halo de Solyth", "accessory", DamageElement.HOLY, Stat.HEALING_DONE_PERCENT, .20, Rarity.RARO),
    ("veil_shroud", "Mortalha do Inominável", "body", DamageElement.SHADOW, Stat.LIFESTEAL_PERCENT, .04, Rarity.RARO),
    ("fractured_page", "Página de Nyxelle", "accessory", DamageElement.ARCANE, Stat.MAX_RESOURCE, 4, Rarity.RARO),
    ("destiny_thread", "Fio do Destino", "accessory", None, Stat.PROC_CHANCE_PERCENT, .10, Rarity.LENDARIO),
):
    EQUIPMENT_DEFS[_iid] = EquipmentDef(id=_iid, name=_name, slot=_slot, required_element=_element,
        rarity=_rarity, random_drop=False,
        modifiers=[Modifier(stat=_stat, kind=ModifierKind.FLAT, value=_value, source=_iid)])


def enchantment_choices(character) -> list[str]:
    return [eid for eid, enchant in ENCHANTMENT_DEFS.items()
            if enchant.required_element not in character.sealed_elements]


def compatible_piece(piece, character) -> bool:
    item = EQUIPMENT_DEFS[piece.definition_id]
    return (item.required_element not in character.sealed_elements
            and all(ENCHANTMENT_DEFS[e].required_element not in character.sealed_elements for e in piece.enchantments))


def equipped_item_ids(character: Character) -> list[str]:
    """Every equipped item instance -- the 3 armor slot values plus the
    accessory list -- used both to aggregate modifiers and as the key
    space for Character.item_enchantments."""
    return [*character.equipped_armor.values(), *character.equipped_accessories,
            *([character.equipped_weapon_id] if character.equipped_weapon_id else [])]


def item_definition(holder, item_id: str) -> EquipmentDef | None:
    piece = holder.equipment_instances.get(item_id)
    return EQUIPMENT_DEFS.get(piece.definition_id if piece else item_id)


def item_enchantments(character: Character, item_id: str) -> list[str]:
    piece = character.equipment_instances.get(item_id)
    return piece.enchantments if piece else character.item_enchantments.get(item_id, [])


def equipped_sets(character: Character) -> Counter:
    return Counter(item.set_id for iid in character.equipped_armor.values()
                   if (item := item_definition(character, iid)) and item.set_id)


def _armor_set_bonus_modifiers(character: Character) -> list[Modifier]:
    """Only equipped_armor counts toward a set (accessories have no
    set_id by design, per the doc). 2 pieces of the same set_id grant
    the 2-piece bonus; all 3 (the fixed cap) additionally grant the
    3-piece bonus -- both stack, matching how ArmorSetDef stores them
    as separate lists rather than one replacing the other."""
    modifiers: list[Modifier] = []
    for set_id, count in equipped_sets(character).items():
        armor_set = ARMOR_SET_DEFS.get(set_id)
        if armor_set is None:
            continue
        if count >= 2:
            modifiers.extend(armor_set.two_piece_modifiers)
        if count >= 3:
            modifiers.extend(armor_set.three_piece_modifiers)
    return modifiers


def item_modifiers_for(character: Character) -> list[Modifier]:
    modifiers: list[Modifier] = []
    for item_id in equipped_item_ids(character):
        item = item_definition(character, item_id)
        if item is not None:
            modifiers.extend(item.modifiers)
        for enchantment_id in item_enchantments(character, item_id):
            enchantment = ENCHANTMENT_DEFS.get(enchantment_id)
            if enchantment is not None:
                modifiers.extend(enchantment.modifiers)
    modifiers.extend(_armor_set_bonus_modifiers(character))
    return modifiers


def item_triggered_effects_for(character: Character) -> list[TriggeredEffect]:
    effects: list[TriggeredEffect] = []
    for item_id in equipped_item_ids(character):
        item = item_definition(character, item_id)
        if item:
            effects.extend(item.triggered_effects)
        for enchantment_id in item_enchantments(character, item_id):
            enchantment = ENCHANTMENT_DEFS.get(enchantment_id)
            if enchantment is not None:
                effects.extend(enchantment.triggered_effects)
    for set_id, count in equipped_sets(character).items():
        if count >= 3 and set_id in ARMOR_SET_DEFS:
            effects.extend(ARMOR_SET_DEFS[set_id].three_piece_effects)
    return effects
