from wyrdfall.domain.models import (
    Effect,
    EffectKind,
    Modifier,
    ModifierKind,
    Stat,
    StatusEffectDef,
    TriggerEvent,
)

STATUS_DEFS: dict[str, StatusEffectDef] = {
    "guarding": StatusEffectDef(
        id="guarding",
        name="Defendendo",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.MORE, value=1.0, source="guarding")],
    ),
    "marked": StatusEffectDef(
        id="marked",
        name="Marcado",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.PERCENT, value=-0.30, source="marked")],
    ),
    "poisoned": StatusEffectDef(
        id="poisoned",
        name="Envenenado",
        max_stacks=3,
        tick_trigger=TriggerEvent.ON_TURN_START,
        tick_effect=Effect(kind=EffectKind.DAMAGE, amount=2.0),
    ),
    "weakened": StatusEffectDef(
        id="weakened",
        name="Enfraquecido",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=-0.25, source="weakened")],
    ),
    "bleeding": StatusEffectDef(
        id="bleeding",
        name="Sangrando",
        max_stacks=3,
        tick_trigger=TriggerEvent.ON_TURN_START,
        tick_effect=Effect(kind=EffectKind.DAMAGE, amount=3.0),
    ),
    "empowered": StatusEffectDef(
        id="empowered",
        name="Fortalecido",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.20, source="empowered")],
    ),
    # Fase 7 -- Licantropo's trait "Sangue Selvagem" (docs/design/
    # 04-racas.md): re-applied every one of the character's own turns by
    # a trait_triggered_effect (see races.py), stacking without ever
    # naturally expiring mid-combat (verified against combat.py's actual
    # ON_TURN_START-before-_tick_statuses order). max_stacks=999
    # approximates the doc's "empilhável sem limite" as a high finite
    # cap rather than true infinity, which the data model has no concept
    # of. +2% Ataque per stack is a first-guess balance number.
    # Orc's Segundo Fôlego (04-racas.md, domain/race_evolution.py)
    "segundo_folego": StatusEffectDef(
        id="segundo_folego",
        name="Segundo Fôlego",
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.25, source="segundo_folego")],
    ),
    "instinto_selvagem": StatusEffectDef(
        id="instinto_selvagem",
        name="Instinto Selvagem",
        max_stacks=999,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.02, source="instinto_selvagem")],
    ),
    # -- Fase 7 -- Área 3, O Pico Silente (docs/design/12-monstros.md
    # §3.3). "Estoura em Congelamento" (a stack-threshold burst into a
    # separate stun status) is cut -- no stack-threshold-triggers-effect
    # mechanism exists in combat.py today; the debuff itself is real and
    # stacking regardless.
    "lentidao": StatusEffectDef(
        id="lentidao",
        name="Lentidão",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=-3.0, source="lentidao")],
    ),
    "fragilidade_ao_gelo": StatusEffectDef(
        id="fragilidade_ao_gelo",
        name="Fragilidade ao Gelo",
        max_stacks=5,
        modifiers=[Modifier(stat=Stat.ICE_RESIST, kind=ModifierKind.FLAT, value=-0.10, source="fragilidade_ao_gelo")],
    ),
    # A Viúva de Gelo's final-phase "Ventania Final" enrage timer
    # (13-chefes.md §3), approximated as a real self-stacking buff
    # applied every one of her own turns -- same working pattern as
    # instinto_selvagem above -- rather than the literal "timer" the doc
    # describes, which has no engine concept to hook into today.
    "ventania_final": StatusEffectDef(
        id="ventania_final",
        name="Ventania Final",
        max_stacks=999,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.05, source="ventania_final")],
    ),
    # -- Fase 7 -- Área 4, A Tempestade Eterna (docs/design/12-monstros.md
    # §3.4): Arauto da Tempestade's buff. The doc conditions this on "ao
    # lançar dano de Raio" -- simplified to its own castable buff ability
    # (same shape as living_bellows' bellows_empower) rather than a
    # damage-triggered proc, since one ability's effects can't split
    # between "damage this target" and "buff my allies" under the
    # current Ability/TargetMode model.
    "acelerado": StatusEffectDef(
        id="acelerado",
        name="Acelerado",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=3.0, source="acelerado")],
    ),
    # -- Fase 7 -- Área 5, As Profundezas Afogadas (docs/design/
    # 11-habilidades.md §8.3, "Reações Elementais"): Encharcado's
    # complete mechanical definition per the doc is exactly these two
    # conditional Modifiers -- "não faz nada sozinho" (does nothing on
    # its own, no direct damage/DoT). Amplifies Raio damage taken
    # (negative lightning_resist) and reduces Fogo damage taken
    # (positive fire_resist) while active -- same "status is just a
    # Modifier on a resist stat" shape as fragilidade_ao_gelo.
    "encharcado": StatusEffectDef(
        id="encharcado",
        name="Encharcado",
        max_stacks=1,
        modifiers=[
            Modifier(stat=Stat.LIGHTNING_RESIST, kind=ModifierKind.FLAT, value=-0.5, source="encharcado"),
            Modifier(stat=Stat.FIRE_RESIST, kind=ModifierKind.FLAT, value=0.3, source="encharcado"),
        ],
    ),
    # Maremoto's "Fúria da Maré" (13-chefes.md §5) -- a heavier version
    # of lentidao (Área 3), same shape, bigger magnitude.
    "correnteza": StatusEffectDef(
        id="correnteza",
        name="Correnteza",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=-6.0, source="correnteza")],
    ),
    # -- Fase 7 -- Área 6, As Minas Esquecidas (docs/design/02-elementos.md):
    # Terra's element-wide mechanic -- "reduz a Defesa física do alvo por
    # um tempo" -- same shape as the existing "marked". The Terra<->Ar
    # mutual-exclusion reaction with Desequilibrado (11-habilidades.md
    # §8.3) is deferred until Área 7 ships Desequilibrado too -- the
    # check would be a no-op with only one half of the pair existing.
    "fragmentado": StatusEffectDef(
        id="fragmentado",
        name="Fragmentado",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.PERCENT, value=-0.25, source="fragmentado")],
        exclusive_with="desequilibrado",
    ),
    # -- Fase 7 -- Área 7, Os Pináculos Flutuantes (docs/design/
    # 02-elementos.md): Ar's element-wide mechanic -- "reduz a Esquiva e
    # o Bloqueio do alvo". Mutually exclusive with Fragmentado (Terra),
    # per the Terra<->Ar Reação Elemental (11-habilidades.md §8.3).
    "desequilibrado": StatusEffectDef(
        id="desequilibrado",
        name="Desequilibrado",
        max_stacks=1,
        modifiers=[
            Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=-0.15, source="desequilibrado"),
            Modifier(stat=Stat.BLOCK_CHANCE, kind=ModifierKind.FLAT, value=-0.15, source="desequilibrado"),
        ],
        exclusive_with="fragmentado",
    ),
    # -- Fase 7 -- Área 9, O Santuário Desmoronado (docs/design/
    # 02-elementos.md): Cantor de Hinos's signature. Same stat
    # Renascido's own racial penalty already proved out
    # (HEALING_RECEIVED_PERCENT), just as a status instead of a trait.
    "amaldicoado": StatusEffectDef(
        id="amaldicoado",
        name="Amaldiçoado",
        max_stacks=1,
        modifiers=[
            Modifier(stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=-0.4, source="amaldicoado"),
        ],
    ),
    # -- Fase 7 -- Área 10, A Sombra Sob o Véu. Sussurro's signature.
    # Kept as id="fear" (English) rather than "medo" specifically so
    # the 3 existing status_immunities={"fear"} declarations
    # (Renascido/Construto races, Área 9's Guardião de Luz) become real
    # and reachable instead of staying disclosed-as-inert. Same
    # Control-flavored ATTACK debuff shape/numbers as "weakened".
    "fear": StatusEffectDef(
        id="fear",
        name="Medo",
        max_stacks=1,
        fail_chance=0.30,  # 01-mecanicas.md §4: the action may collapse into Defender
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=-0.25, source="fear")],
    ),
    # Arauto do Véu's signature -- "aumenta a Esquiva dos aliados próximos".
    "esquiva_sombria": StatusEffectDef(
        id="esquiva_sombria",
        name="Esquiva Sombria",
        max_stacks=1,
        modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.15, source="esquiva_sombria")],
    ),
    # A Tecelã Desfeita's "Fio Partido" real enrage timer (13-chefes.md
    # §12), approximated exactly like Viúva de Gelo's ventania_final
    # above -- a real self-stacking buff applied every one of her own
    # turns in that phase, rather than a literal per-turn timer, which
    # has no engine concept to hook into.
    "fio_partido": StatusEffectDef(
        id="fio_partido",
        name="Fio Partido",
        max_stacks=999,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.05, source="fio_partido")],
    ),
    # docs/design/01-mecanicas.md §4 -- the two control statuses the engine
    # now respects beyond stat modifiers: Silêncio and Provocar.
    "silencio": StatusEffectDef(
        id="silencio",
        name="Silêncio",
        max_stacks=1,
        silences=True,
    ),
    "provocado": StatusEffectDef(
        id="provocado",
        name="Provocado",
        max_stacks=1,
        taunts=True,
    ),
    # docs/design/11-habilidades.md §8.4 -- Combo em Equipe: a short mark
    # with no effect of its own; a different ally's hit cashes it in.
    "marcado_para_combo": StatusEffectDef(
        id="marcado_para_combo",
        name="Marcado para Combo",
        max_stacks=1,
        team_combo_bonus=0.5,
    ),
}
