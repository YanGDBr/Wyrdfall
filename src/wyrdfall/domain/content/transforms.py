"""TRANSFORM forms (docs/design/11-habilidades.md §5). The Licantropo's
Forma de Fera (04-racas.md: "ao atingir um número alto de stacks de
Instinto num único combate, transforma-se ... pelo resto daquele
combate") -- CombatEngine flips it at combat.py::LYCAN_TRANSFORM_STACKS."""

from wyrdfall.domain.character import TransformDef
from wyrdfall.domain.models import DamageElement, Modifier, ModifierKind, Stat, element_tag


def _dual_form(form_id: str, name: str, glyph: str, element: DamageElement, opposite_resist: Stat) -> TransformDef:
    """Natureza Dual (04-racas.md Meio-celestial): "+40% de dano/efeito
    daquele elemento e -20% de resistência ao elemento oposto enquanto
    ativa" -- rest of the combat, kit untouched."""
    return TransformDef(
        id=form_id, name=name, glyph=glyph,
        description=f"+40% de dano {element.value} e -20% de resistência ao elemento oposto até o fim do combate.",
        modifiers=[
            Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.40, source=form_id, tags=[element_tag(element)]),
            Modifier(stat=opposite_resist, kind=ModifierKind.FLAT, value=-0.20, source=form_id),
        ],
    )


TRANSFORM_DEFS: dict[str, TransformDef] = {
    "forma_de_fera": TransformDef(
        id="forma_de_fera",
        name="Forma de Fera",
        description="O Instinto toma conta: +30% de Ataque, +20% de dano físico, +5 de Velocidade, 25% de roubo de "
                    "vida e um kit de fera até o fim do combate.",
        modifiers=[
            Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.30, source="forma_de_fera"),
            Modifier(stat=Stat.PHYSICAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.20, source="forma_de_fera"),
            Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=5.0, source="forma_de_fera"),
            Modifier(stat=Stat.LIFESTEAL_PERCENT, kind=ModifierKind.FLAT, value=0.25, source="forma_de_fera"),
        ],
        granted_abilities=["fera_dilacerar", "fera_mordida_voraz", "fera_uivo"],
        glyph="/\\_/\\",
    ),
    "forma_sagrada": _dual_form("forma_sagrada", "Forma Sagrada", "(+)", DamageElement.HOLY, Stat.SHADOW_RESIST),
    "forma_sombria": _dual_form("forma_sombria", "Forma Sombria", "(-)", DamageElement.SHADOW, Stat.HOLY_RESIST),
}
