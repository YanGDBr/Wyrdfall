"""Invocações de combate (docs/design/11-habilidades.md §5 SUMMON): temporary
combatants for one fight -- not the Companheiro (domain/companions.py).
Their abilities carry no archetype_weight, same rule as companions."""

from wyrdfall.domain.character import SummonDef
from wyrdfall.domain.models import StatBlock

SUMMON_DEFS: dict[str, SummonDef] = {
    "espectro": SummonDef(
        id="espectro", name="Espectro",
        base_stats=StatBlock(max_hp=8, attack=3, defense=0, speed=7, dodge_chance=0.2, max_resource=0),
        abilities=["summon_spectral_touch"], tags=["undead", "summon"],
    ),
    "lobo_de_sombra": SummonDef(
        id="lobo_de_sombra", name="Lobo de Sombra",
        base_stats=StatBlock(max_hp=12, attack=4, defense=1, speed=8, max_resource=0),
        abilities=["companion_bite"], tags=["beast", "summon"],
    ),
    "broto_putrido": SummonDef(
        id="broto_putrido", name="Broto Pútrido",
        base_stats=StatBlock(max_hp=14, attack=4, defense=1, speed=5, poison_resist=0.6, max_resource=0),
        abilities=["putrid_mother_bite"], tags=["beast", "summon"],
    ),
    "copia_rascunhada": SummonDef(
        id="copia_rascunhada", name="Cópia Rascunhada",
        base_stats=StatBlock(max_hp=6, attack=2, defense=0, speed=4, max_resource=0),
        abilities=["summon_ink_smear"], tags=["construct", "summon"],
    ),
}
