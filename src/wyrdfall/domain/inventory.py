"""Instance creation, legacy migration and read-only equipment comparisons."""
from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from wyrdfall.domain.gear import EquipmentInstance
from wyrdfall.domain.items import EQUIPMENT_DEFS, ENCHANTMENT_DEFS, ENCHANTMENT_SLOTS_BY_RARITY, equipped_item_ids, item_definition


def add_equipment(run, definition_id: str, *, owner_id=None, enchantments=()) -> EquipmentInstance:
    definition = EQUIPMENT_DEFS[definition_id]
    run.equipment_sequence += 1
    iid = "gear_" + uuid5(NAMESPACE_URL, f"wyrdfall:{run.run_id}:{run.equipment_sequence}").hex
    piece = EquipmentInstance(id=iid, definition_id=definition_id, rarity=definition.rarity.value,
                              owner_id=owner_id, enchantments=list(enchantments))
    run.equipment_instances[iid] = piece
    run.inventory.append(iid)
    return piece


def sync_equipment(run, character) -> None:
    character.equipment_instances = {iid: run.equipment_instances[iid] for iid in equipped_item_ids(character)
                                     if iid in run.equipment_instances}
    # Keep the old field readable for old combat snapshots and tooling.
    character.item_enchantments = {iid: list(piece.enchantments)
                                   for iid, piece in character.equipment_instances.items()}


def migrate_inventory(run) -> None:
    """Old saves list definition IDs, possibly repeated. Allocate each copy once.

    Legacy unequipped enchantments belong to the next free copy, never to every
    identical piece. Invalid missing copies are recovered from equipped slots.
    """
    for iid, piece in run.equipment_instances.items():
        if piece.id != iid or piece.definition_id not in EQUIPMENT_DEFS:
            raise ValueError("Identidade de equipamento inválida no save.")
        if (any(e not in ENCHANTMENT_DEFS for e in piece.enchantments)
                or len(piece.enchantments) > ENCHANTMENT_SLOTS_BY_RARITY[piece.rarity]
                or len(set(piece.enchantments)) != len(piece.enchantments)):
            raise ValueError("Encantamentos inválidos no save.")
    old = list(run.inventory)
    run.inventory = []
    for iid in old:
        if iid in run.equipment_instances:
            if iid not in run.inventory:
                run.inventory.append(iid)
        elif iid in EQUIPMENT_DEFS:
            add_equipment(run, iid)
        else:
            raise ValueError(f"Equipamento desconhecido no save: {iid}")
    used = set()
    for hero in run.party:
        old_enchants = dict(hero.item_enchantments)

        def resolve(iid):
            if iid in run.equipment_instances:
                if iid in used:
                    raise ValueError("Uma peça aparece equipada em mais de um slot no save.")
                piece = run.equipment_instances[iid]
                if piece.owner_id not in (None, hero.id):
                    raise ValueError("Posse de equipamento inconsistente no save.")
            else:
                if iid not in EQUIPMENT_DEFS:
                    raise ValueError(f"Equipamento desconhecido no save: {iid}")
                piece = next((p for p in run.equipment_instances.values()
                              if p.definition_id == iid and p.id not in used and p.owner_id in (None, hero.id)), None)
                if piece is None:
                    piece = add_equipment(run, iid)
                piece.enchantments = list(old_enchants.pop(iid, []))
            used.add(piece.id)
            piece.owner_id = hero.id
            return piece.id

        hero.equipped_armor = {slot: resolve(iid) for slot, iid in hero.equipped_armor.items()}
        hero.equipped_accessories = [resolve(iid) for iid in hero.equipped_accessories]
        if hero.equipped_weapon_id:
            hero.equipped_weapon_id = resolve(hero.equipped_weapon_id)
        for definition_id, enchantments in old_enchants.items():
            if definition_id not in EQUIPMENT_DEFS or not enchantments:
                continue
            piece = next((p for p in run.equipment_instances.values() if p.definition_id == definition_id
                          and p.id not in used and p.owner_id is None), None)
            if piece:
                piece.owner_id = hero.id
                piece.enchantments = list(enchantments)
        sync_equipment(run, hero)


def initialize_weapons(run) -> None:
    from wyrdfall.domain.weapons import WEAPON_TYPE_DEFS
    for hero in run.party:
        if hero.id in run.equipment_initialized_for:
            continue
        for weapon_type in WEAPON_TYPE_DEFS:
            piece = add_equipment(run, f"basic_{weapon_type}", owner_id=hero.id)
            if hero.equipped_weapon_type == weapon_type and not hero.equipped_weapon_id:
                hero.equipped_weapon_id = piece.id
        run.equipment_initialized_for.add(hero.id)
        sync_equipment(run, hero)


def equipment_comparison(run, hero, item_id, ruleset, talent_tree) -> str:
    """Preview on a copy, including lost set bonuses and weapon scaling."""
    from wyrdfall.domain.factory import recompute_passive_effects
    from wyrdfall.domain.items import ARMOR_SET_DEFS, ENCHANTMENT_DEFS, equipped_sets
    item = item_definition(run, item_id)
    if item is None:
        return ""
    preview = hero.model_copy(deep=True)
    if item.slot == "weapon":
        preview.equipped_weapon_id = item_id
        preview.equipped_weapon_type = item.weapon_type_id
    elif item.slot == "accessory":
        if item_id in preview.equipped_accessories or len(preview.equipped_accessories) >= 3:
            return "Remova um acessório para comparar este encaixe."
        preview.equipped_accessories.append(item_id)
    else:
        preview.equipped_armor[item.slot] = item_id
    sync_equipment(run, preview)
    recompute_passive_effects(preview, talent_tree)
    before, after = hero.computed_stats(ruleset), preview.computed_stats(ruleset)
    labels = {"max_hp": "PV máximo", "attack": "Ataque", "defense": "Defesa", "speed": "Velocidade",
              "crit_chance": "Chance de crítico", "crit_mult": "Dano crítico", "max_resource": "Recurso máximo",
              "dodge_chance": "Esquiva", "block_chance": "Bloqueio", "block_percent": "Redução ao bloquear",
              "weapon_damage_percent": "Dano da arma", "status_resist": "Resistência a status",
              "healing_done_percent": "Cura causada", "healing_received_percent": "Cura recebida",
              "physical_damage_percent": "Dano físico", "elemental_damage_percent": "Dano elemental",
              "lifesteal_percent": "Roubo de vida", "armor_penetration_percent": "Penetração"}
    changes = []
    for stat in type(after).model_fields:
        a, b = getattr(before, stat), getattr(after, stat)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(b - a) > 0.00001:
            percentage = stat.endswith(("percent", "chance", "resist"))
            delta = f"{(b-a)*100:+.1f} p.p." if percentage else f"{b-a:+.1f}"
            changes.append(f"{labels.get(stat, stat)}: {delta}")
    from wyrdfall.domain.models import DamageElement
    element_names = {"fire": "Fogo", "ice": "Gelo", "lightning": "Raio", "water": "Água", "earth": "Terra",
                     "air": "Ar", "poison": "Veneno", "holy": "Sagrado", "shadow": "Sombrio", "arcane": "Arcano"}
    for element in DamageElement:
        if element == DamageElement.PHYSICAL:
            continue
        delta = preview.element_damage_bonus(ruleset, element) - hero.element_damage_bonus(ruleset, element)
        if abs(delta) > .00001:
            changes.append(f"Bônus de {element_names[element.value]}: {delta*100:+.1f} p.p.")
    sets_before, sets_after = equipped_sets(hero), equipped_sets(preview)
    for sid in sets_before.keys() | sets_after.keys():
        if sets_before[sid] != sets_after[sid]:
            armor_set = ARMOR_SET_DEFS[sid]
            changes.append(f"{armor_set.name}: {sets_before[sid]} → {sets_after[sid]}/3. {armor_set.description}")
    piece = run.equipment_instances[item_id]
    enchants = ", ".join(ENCHANTMENT_DEFS[e].name for e in piece.enchantments)
    for old_id in set(equipped_item_ids(hero)) - set(equipped_item_ids(preview)):
        old_item = item_definition(run, old_id)
        old_piece = run.equipment_instances[old_id]
        old_enchants = ", ".join(ENCHANTMENT_DEFS[e].name for e in old_piece.enchantments) or "sem encantamentos"
        changes.append(f"Sai {old_item.name}: {old_enchants}. {old_item.description}")
    return " · ".join(changes or ["Sem mudança de atributos"]) + (f" | {enchants}" if enchants else " | Sem encantamentos") + (f" | {item.description}" if item.description else "")
