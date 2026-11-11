from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.challenges import ChallengeDef, ChallengeKind
from wyrdfall.domain.models import Archetype, DamageElement, Effect, EffectKind, Stat

ABILITY_DEFS: dict[str, Ability] = {
    # -- Runeguard (Guerreiro) base kit -----------------------------------
    "strike": Ability(
        id="strike",
        name="Strike",
        description="Um golpe firme de arma.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0, poise_damage=3.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    # docs/design/10-sistemas-de-build.md §3.9 -- "Defender (Block)": the
    # universal action every character has from the start, outside the
    # Active Ability Slot budget. Mechanically the MVP's Guard, as the doc
    # itself says; the id stays "guard" (kits/tests reference it).
    "guard": Ability(
        id="guard",
        name="Defender",
        description="Prepare-se, dobrando sua Defesa até seu próximo turno.",
        resource_cost=0,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="guarding", duration=1, stacks=1)],
        universal=True,
    ),
    "taunt": Ability(
        id="taunt",
        name="Provocar",
        description="Chama a atenção de todos os inimigos -- eles só conseguem mirar em você por 2 turnos.",
        resource_cost=1,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="provocado", duration=2)],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
        role="Controle",
    ),
    "focus": Ability(
        id="focus",
        name="Focus",
        description="Acalme sua mente, ganhando Resolução para gastar em golpes rúnicos.",
        resource_cost=0,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.RESTORE_RESOURCE, amount=2.0)],
    ),
    "rune_smash": Ability(
        id="rune_smash",
        name="Rune Smash",
        description="Canalize Resolução em um golpe rúnico pesado.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.2, poise_damage=6.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    # -- Patrulheiro base kit ----------------------------------------------
    "aimed_shot": Ability(
        id="aimed_shot",
        name="Aimed Shot",
        description="Um disparo calculado à distância.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0, poise_damage=2.0)],
        tags=["ranged", "combo_builder"],  # 11-habilidades.md §8.1: builds Pontos de Combo on hit
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "piercing_shot": Ability(
        id="piercing_shot",
        name="Piercing Shot",
        description="Um tiro que ignora parte da defesa do alvo.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.2, poise_damage=3.0)],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    # -- Místico base kit ---------------------------------------------------
    "arcane_bolt": Ability(
        id="arcane_bolt",
        name="Arcane Bolt",
        description="Um projétil de energia arcana pura.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "arcane_nova": Ability(
        id="arcane_nova",
        name="Arcane Nova",
        description="Uma explosão de energia arcana que atinge todos os inimigos.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.7,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    # -- Guardião base kit ---------------------------------------------------
    "shield_bash": Ability(
        id="shield_bash",
        name="Shield Bash",
        description="Um golpe de escudo que também abala a postura do alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=1.5, scales_with=Stat.ATTACK, scale_factor=0.8, poise_damage=4.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "bulwark_slam": Ability(
        id="bulwark_slam",
        name="Bulwark Slam",
        description="Um golpe pesado apoiado em toda a resistência do Guardião.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.DEFENSE, scale_factor=1.5, poise_damage=5.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    # -- Especializações puras (Fase 5, docs/design/05b-classes-roster.md) --
    "reckless_smash": Ability(
        id="reckless_smash",
        name="Reckless Smash",
        description="Um golpe descuidado e brutal -- a assinatura do Berserker.",
        resource_cost=1,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.8, poise_damage=4.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "multi_shot": Ability(
        id="multi_shot",
        name="Multi Shot",
        description="Uma rajada de flechas contra todos os inimigos -- a assinatura do Arqueiro. Finalizadora: gasta todos os Pontos de Combo.",
        resource_cost=2,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8)],
        tags=["ranged", "combo_finisher"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "rapid_fire": Ability(
        id="rapid_fire",
        name="Rapid Fire",
        description="Uma rajada concentrada num único alvo -- a assinatura do Gunner.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.6, poise_damage=2.0)],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "meteor": Ability(
        id="meteor",
        name="Meteor",
        description="Uma explosão de energia arcana devastadora -- a assinatura do Mago.",
        resource_cost=4,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "unshakable": Ability(
        id="unshakable",
        name="Unshakable",
        description="Ergue um escudo apoiado em toda a resistência do Colosso.",
        resource_cost=1,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=4.0, scales_with=Stat.DEFENSE, scale_factor=1.0)],
    ),
    "annihilate": Ability(
        id="annihilate",
        name="Annihilate",
        description="O golpe supremo do Avatar da Guerra.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=8.0, scales_with=Stat.ATTACK, scale_factor=2.0, poise_damage=8.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "true_strike": Ability(
        id="true_strike",
        name="True Strike",
        description="Um tiro que nunca erra o ponto certo -- a assinatura do Predador Absoluto.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.8, poise_damage=3.0)],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "arcane_devastation": Ability(
        id="arcane_devastation",
        name="Arcane Devastation",
        description="Tudo o que sobrou da build vira pura energia arcana -- a assinatura do Tecelão do Véu.",
        resource_cost=4,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.3,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "fortress": Ability(
        id="fortress",
        name="Fortress",
        description="Um bastião de escudo praticamente impossível de derrubar.",
        resource_cost=2,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=8.0, scales_with=Stat.DEFENSE, scale_factor=1.5)],
    ),
    # -- Fase 7 -- kits reais para as 7 Especializações Fase 5b genuinamente
    # alcançáveis hoje (docs/design/05b-classes-roster.md; ver domain/
    # specializations.py's docstring pra reachability de cada uma).
    "called_shot": Ability(
        id="called_shot",
        name="Tiro Calculado",
        description="Um disparo preciso, calculado pra acertar em cheio -- a assinatura do Atirador.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.6, poise_damage=3.0)],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "enchanted_blessing": Ability(
        id="enchanted_blessing",
        name="Bênção Encantada",
        description="Fortalece todo o grupo de uma vez -- a assinatura do Encantador.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="empowered", duration=3, stacks=1)],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "steadfast_fist": Ability(
        id="steadfast_fist",
        name="Punho Inabalável",
        description="Um golpe apoiado numa defesa impossível de quebrar -- a assinatura do Punho de Granito.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.DEFENSE, scale_factor=1.0, poise_damage=4.0),
            Effect(kind=EffectKind.APPLY_SHIELD, amount=4.0, scales_with=Stat.DEFENSE, scale_factor=1.0),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "elven_arrow": Ability(
        id="elven_arrow",
        name="Flecha Élfica",
        description="Uma flecha imbuída de energia arcana -- a assinatura do Arqueiro Élfico.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.5,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "unbridled_fury": Ability(
        id="unbridled_fury",
        name="Fúria Desmedida",
        description="Queima toda a fúria acumulada num só golpe -- a assinatura da Fúria Órquica.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=2.0, poise_damage=5.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "spectral_cut": Ability(
        id="spectral_cut",
        name="Corte Espectral",
        description="Um golpe sombrio que rouba um pouco da vida do alvo -- a assinatura da Lâmina Espectral.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.6,
                damage_element=DamageElement.SHADOW,
            )
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "wild_howl": Ability(
        id="wild_howl",
        name="Uivo Selvagem",
        description="Um uivo que acelera o próprio instinto de batalha -- a assinatura do Uivo Selvagem.",
        resource_cost=2,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="instinto_selvagem", duration=2, stacks=3)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    # -- Fase 7 -- assinaturas de Alinhamento alcançáveis desde que Eventos
    # escrevem alignment_score (docs/design/05-classes.md §4: Bondoso troca
    # dano por cura/suporte, Maligno troca sustentação por dano/dreno).
    "forest_embrace": Ability(
        id="forest_embrace",
        name="Abraço da Floresta",
        description="Raízes envolvem todo o grupo e fecham feridas -- a assinatura do Guardião da Floresta.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.HEAL, amount=3.0, scales_with=Stat.DEFENSE, scale_factor=0.8)],
        tags=["magic"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "cursed_blow": Ability(
        id="cursed_blow",
        name="Golpe Maldito",
        description="Um golpe que deixa uma maldição pra trás -- a assinatura do Cavaleiro Negro.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.5,
                damage_element=DamageElement.SHADOW,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="amaldicoado", duration=3, stacks=1),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "plague": Ability(
        id="plague",
        name="Praga",
        description="Uma nuvem de peste sobre todos os inimigos -- a assinatura do Senhor da Peste.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8,
                damage_element=DamageElement.POISON,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1),
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    # -- Estágio 2 (Fase 8, docs/design/05b-classes-roster.md §10) -- one
    # signature per Stage-2 keystone (domain/content/specializations.py).
    # Four of them carry the Minigames de Habilidade of 11-habilidades.md
    # §9 (the only abilities in the game that do -- §9's containment rule):
    # Sequência, Canalização, Precisão and Janela de Tempo respectively.
    "storm_of_blows": Ability(
        id="storm_of_blows",
        name="Tempestade de Golpes",
        description="Três golpes em cadeia -- repita a sequência pra acertar todos (Sequência). Combo: +50% depois de Reckless Smash.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        combo_from=["reckless_smash"],
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.9, poise_damage=2.0),
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.9, poise_damage=2.0),
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.9, poise_damage=2.0),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
        challenge=ChallengeDef(kind=ChallengeKind.SEQUENCE, sequence_length=4, min_factor=0.5),
    ),
    "war_incarnate": Ability(
        id="war_incarnate",
        name="Guerra Encarnada",
        description="Um único golpe com tudo que há -- a assinatura da Encarnação da Batalha.",
        resource_cost=4,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=10.0, scales_with=Stat.ATTACK, scale_factor=2.4, poise_damage=6.0,
                execute_threshold=0.30, execute_bonus=1.0,  # Execução: dobra contra alvos abaixo de 30%
            )
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "ruinous_edict": Ability(
        id="ruinous_edict",
        name="Édito da Ruína",
        description="Amaldiçoa todos os inimigos e os fere com sombras -- a assinatura do Lorde da Ruína.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.SHADOW),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="amaldicoado", duration=2),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "horde_call": Ability(
        id="horde_call",
        name="Chamado da Horda",
        description="Fortalece o grupo inteiro e enfraquece o alvo -- a assinatura do Senhor da Horda.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.4),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="weakened", duration=2),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "reap_the_thread": Ability(
        id="reap_the_thread",
        name="Ceifar o Fio",
        description="Corta e drena -- a assinatura do Ceifador Espectral. Custa 15% do PV atual (Sangue).",
        resource_cost=0.15,
        pays_with_hp=True,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.6, damage_element=DamageElement.SHADOW),
            Effect(kind=EffectKind.HEAL, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.4),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "alpha_howl": Ability(
        id="alpha_howl",
        name="Uivo do Alfa",
        description="Instinto selvagem pra todo o grupo -- a assinatura do Alfa.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="instinto_selvagem", duration=3)],
        tags=["melee"],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "master_volley": Ability(
        id="master_volley",
        name="Salva do Mestre",
        description="Duas flechas em cada inimigo -- a assinatura do Mestre Arqueiro.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8),
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8),
        ],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "deadeye_round": Ability(
        id="deadeye_round",
        name="Bala Certeira",
        description="Um único tiro devastador -- a assinatura do Pistoleiro.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=8.0, scales_with=Stat.ATTACK, scale_factor=2.0, poise_damage=5.0)],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "fortune_shot": Ability(
        id="fortune_shot",
        name="Tiro da Fortuna",
        description="Escolha o ponto certo e o crítico é garantido (Precisão) -- a assinatura do Caçador de Tesouros.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.6)],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
        challenge=ChallengeDef(kind=ChallengeKind.PRECISION, zone_count=3, min_factor=1.0, crit_on_perfect=True),
    ),
    "unseen_strike": Ability(
        id="unseen_strike",
        name="Golpe Invisível",
        description="Ataca da sombra e some -- a assinatura da Sombra da Mata.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=7.0, scales_with=Stat.ATTACK, scale_factor=1.8),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="esquiva_sombria", duration=2),
        ],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "moonlit_arrow": Ability(
        id="moonlit_arrow",
        name="Flecha do Luar",
        description="Luz sagrada na ponta da flecha -- a assinatura do Olho da Lua.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=7.0, scales_with=Stat.ATTACK, scale_factor=1.7,
                damage_element=DamageElement.HOLY, bonus_vs_tags=["undead", "cursed"], bonus_vs_tags_bonus=0.5,
            ),
        ],
        tags=["ranged"],
        archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "arcane_cataclysm": Ability(
        id="arcane_cataclysm",
        name="Cataclismo Arcano",
        description="Canalize e mantenha o foco -- quanto mais tempo, mais forte (Canalização) -- a assinatura do Arquimago. Recarga: 3 turnos.",
        resource_cost=4,
        cooldown_turns=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=8.0, scales_with=Stat.ATTACK, scale_factor=1.6, damage_element=DamageElement.ARCANE),
        ],
        tags=["magic", "channeled"],
        archetype_weight={Archetype.MISTICO: 1.0},
        challenge=ChallengeDef(kind=ChallengeKind.CHANNEL, duration_seconds=3.0, min_factor=0.4),
    ),
    "wyrd_song": Ability(
        id="wyrd_song",
        name="Canção do Wyrd",
        description="Cura e acelera o grupo -- a assinatura do Cantor do Wyrd.",
        resource_cost=4,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[
            Effect(kind=EffectKind.HEAL, amount=5.0, scales_with=Stat.ATTACK, scale_factor=0.6),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="acelerado", duration=2),
            # REVIVE (11-habilidades.md §5): the rare in-combat revive, 25% PV
            Effect(kind=EffectKind.REVIVE, amount=0.25),
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "veil_reading": Ability(
        id="veil_reading",
        name="Leitura do Véu",
        description="Fragmenta o alvo e drena sua Resolução -- a assinatura do Oráculo do Véu.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.5, damage_element=DamageElement.ARCANE),
            Effect(kind=EffectKind.DRAIN_RESOURCE, amount=3.0),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="fragmentado", duration=2),
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "plague_herald": Ability(
        id="plague_herald",
        name="Arauto da Praga",
        description="Veneno pesado em todos -- a assinatura do Arauto da Praga.",
        resource_cost=4,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.POISON),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=4, stacks=2),
        ],
        tags=["magic"],
        archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "titanic_blow": Ability(
        id="titanic_blow",
        name="Golpe Titânico",
        description="Acerte a janela pra descarregar tudo (Janela de Tempo) -- a assinatura do Titã. Recarga: 2 turnos.",
        resource_cost=3,
        cooldown_turns=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=9.0, scales_with=Stat.ATTACK, scale_factor=2.0, poise_damage=8.0)],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
        challenge=ChallengeDef(kind=ChallengeKind.TIMING, min_factor=0.6),
    ),
    "living_rampart": Ability(
        id="living_rampart",
        name="Muralha Viva",
        description="Um escudo grande sobre todo o grupo -- a assinatura da Muralha Viva.",
        resource_cost=4,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=6.0, scales_with=Stat.DEFENSE, scale_factor=1.5)],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "heartwood_bloom": Ability(
        id="heartwood_bloom",
        name="Florescer do Cerne",
        description="Cura forte em todo o grupo -- a assinatura do Coração da Floresta. 2 cargas por descanso.",
        resource_cost=4,
        charges_per_rest=2,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[
            Effect(kind=EffectKind.HEAL, amount=8.0, scales_with=Stat.DEFENSE, scale_factor=1.0),
            Effect(kind=EffectKind.CLEANSE, amount=0),  # every harmful status
        ],
        tags=["magic"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "mountain_heart": Ability(
        id="mountain_heart",
        name="Coração da Montanha",
        description="Terra bruta num golpe que desequilibra -- a assinatura do Coração da Montanha.",
        resource_cost=3,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=7.0, scales_with=Stat.DEFENSE, scale_factor=1.6, damage_element=DamageElement.EARTH, poise_damage=6.0),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="desequilibrado", duration=2),
        ],
        tags=["melee"],
        archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    # -- Híbridos de par (Fase 5b's 17, kits from domain/content/
    # specializations.py::_HYBRID_BRANCHES): signatures weighted across
    # both archetypes of the hybrid.
    "hybrid_savage_volley": Ability(
        id="hybrid_savage_volley", name="Rajada Selvagem",
        description="Flechas disparadas com fúria em todos os inimigos -- a assinatura do Arqueiro-Berserker.",
        resource_cost=3, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.9)],
        tags=["ranged"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.PATRULHEIRO: 0.5},
    ),
    "hybrid_furious_shot": Ability(
        id="hybrid_furious_shot", name="Tiro Furioso",
        description="Um tiro à queima-roupa que abala a postura -- a assinatura do Gunner-Berserker.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.5, poise_damage=4.0)],
        tags=["ranged"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.PATRULHEIRO: 0.5},
    ),
    "hybrid_holy_strike": Ability(
        id="hybrid_holy_strike", name="Golpe Sagrado",
        description="Fere com luz e cura quem golpeia -- a assinatura do Paladino.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3, damage_element=DamageElement.HOLY, bonus_vs_tags=['undead', 'cursed'], bonus_vs_tags_bonus=0.5), Effect(kind=EffectKind.HEAL, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.3)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.6, Archetype.MISTICO: 0.4},
    ),
    "hybrid_rune_blade": Ability(
        id="hybrid_rune_blade", name="Lâmina Rúnica",
        description="Uma lâmina gravada de runas que corta com Arcano -- a assinatura do Mago Rúnico.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.4, damage_element=DamageElement.ARCANE)],
        tags=["melee", "magic"], archetype_weight={Archetype.MISTICO: 0.6, Archetype.GUERREIRO: 0.4},
    ),
    "hybrid_arcane_charge": Ability(
        id="hybrid_arcane_charge", name="Ímpeto Arcano",
        description="Investida envolta em energia que ainda escuda o atacante -- a assinatura do Cavaleiro Arcano.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3, damage_element=DamageElement.ARCANE, poise_damage=2.0)],
        tags=["melee", "magic"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.MISTICO: 0.5},
    ),
    "hybrid_knight_strike": Ability(
        id="hybrid_knight_strike", name="Golpe do Cavaleiro",
        description="Um golpe disciplinado que desequilibra -- a assinatura do Cavaleiro.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3, poise_damage=3.0), Effect(kind=EffectKind.APPLY_STATUS, status_id='desequilibrado', duration=1)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.7, Archetype.GUARDIAO: 0.3},
    ),
    "hybrid_armored_crush": Ability(
        id="hybrid_armored_crush", name="Esmagamento Blindado",
        description="Usa o peso da armadura como arma -- a assinatura do Cavaleiro Pesado.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.DEFENSE, scale_factor=1.5, poise_damage=4.0)],
        tags=["melee"], archetype_weight={Archetype.GUARDIAO: 0.6, Archetype.GUERREIRO: 0.4},
    ),
    "hybrid_juggernaut_rush": Ability(
        id="hybrid_juggernaut_rush", name="Avalanche",
        description="Atropela todos os inimigos -- a assinatura do Juggernaut.",
        resource_cost=3, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.9, poise_damage=3.0)],
        tags=["melee", "cleave"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.GUARDIAO: 0.5},
    ),
    "hybrid_beast_command": Ability(
        id="hybrid_beast_command", name="Comando da Fera",
        description="Um comando que fortalece o grupo (e a fera) -- a assinatura do Domador.",
        resource_cost=2, target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id='instinto_selvagem', duration=2)],
        tags=["ranged"], archetype_weight={Archetype.PATRULHEIRO: 0.6, Archetype.MISTICO: 0.4},
    ),
    "hybrid_spectral_call": Ability(
        id="hybrid_spectral_call", name="Chamado Espectral",
        description="Invoca um Espectro pra lutar ao seu lado e assusta os inimigos -- a assinatura do Invocador.",
        resource_cost=3, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id='fear', duration=2, chance=0.5), Effect(kind=EffectKind.SUMMON, summon_id="espectro")],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 0.7, Archetype.PATRULHEIRO: 0.3},
    ),
    "hybrid_spellbound_arrow": Ability(
        id="hybrid_spellbound_arrow", name="Flecha Encantada",
        description="Uma flecha carregada de Raio -- a assinatura do Caçador Arcano.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3, damage_element=DamageElement.LIGHTNING, chain_percent=0.5)],
        tags=["ranged", "magic"], archetype_weight={Archetype.PATRULHEIRO: 0.5, Archetype.MISTICO: 0.5},
    ),
    "hybrid_ether_rain": Ability(
        id="hybrid_ether_rain", name="Chuva de Éter",
        description="Flechas de éter sobre todos os inimigos -- a assinatura do Arqueiro-Mago.",
        resource_cost=3, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8, damage_element=DamageElement.ARCANE)],
        tags=["ranged", "magic"], archetype_weight={Archetype.PATRULHEIRO: 0.5, Archetype.MISTICO: 0.5},
    ),
    "hybrid_covering_shot": Ability(
        id="hybrid_covering_shot", name="Tiro de Cobertura",
        description="Fere o alvo e o marca pra um aliado finalizar (Combo em Equipe) -- a assinatura da Sentinela.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="marcado_para_combo", duration=2),
        ],
        tags=["ranged"], archetype_weight={Archetype.PATRULHEIRO: 0.5, Archetype.GUARDIAO: 0.5},
    ),
    "hybrid_marching_wall": Ability(
        id="hybrid_marching_wall", name="Muralha em Marcha",
        description="Escuda o grupo inteiro sem parar de avançar -- a assinatura do Bastião Móvel.",
        resource_cost=3, target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=4.0, scales_with=Stat.DEFENSE, scale_factor=1.0)],
        tags=["melee"], archetype_weight={Archetype.GUARDIAO: 0.7, Archetype.PATRULHEIRO: 0.3},
    ),
    "hybrid_aegis": Ability(
        id="hybrid_aegis", name="Égide",
        description="Escuda e cura um aliado -- a assinatura do Avatar.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ALLY,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=4.0, scales_with=Stat.DEFENSE, scale_factor=1.0), Effect(kind=EffectKind.HEAL, amount=3.0, scales_with=Stat.DEFENSE, scale_factor=0.5)],
        tags=["magic"], archetype_weight={Archetype.GUARDIAO: 0.6, Archetype.MISTICO: 0.4},
    ),
    "hybrid_warding_seal": Ability(
        id="hybrid_warding_seal", name="Selo Protetor",
        description="Um selo arcano que escuda todo o grupo -- a assinatura do Guardião Arcano.",
        resource_cost=3, target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=3.0, scales_with=Stat.DEFENSE, scale_factor=1.0)],
        tags=["magic"], archetype_weight={Archetype.GUARDIAO: 0.5, Archetype.MISTICO: 0.5},
    ),
    "hybrid_armored_prayer": Ability(
        id="hybrid_armored_prayer", name="Prece Blindada",
        description="Cura o grupo por trás da couraça -- a assinatura do Sacerdote Blindado.",
        resource_cost=3, target_mode=TargetMode.ALL_ALLIES,
        effects=[
            Effect(kind=EffectKind.HEAL, amount=4.0, scales_with=Stat.DEFENSE, scale_factor=0.8),
            Effect(kind=EffectKind.CLEANSE, amount=1),  # one harmful status each
        ],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 0.7, Archetype.GUARDIAO: 0.3},
    ),
    # -- Triples, generalists, remaining signatures and the hybrid Stage 2s
    # (05b-classes-roster.md §5-8, §10) -- the roster's last kits.
    "triple_twilight_edge": Ability(
        id="triple_twilight_edge", name="Gume do Crepúsculo",
        description="Corta, dispara e enfeitiça num só movimento -- a assinatura da Lâmina do Crepúsculo.",
        resource_cost=3, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8), Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8, damage_element=DamageElement.SHADOW)],
        tags=["melee", "magic"], archetype_weight={Archetype.GUERREIRO: 0.34, Archetype.PATRULHEIRO: 0.33, Archetype.MISTICO: 0.33},
    ),
    "triple_vanguard_order": Ability(
        id="triple_vanguard_order", name="Ordem de Avanço",
        description="Fortalece e escuda todo o grupo -- a assinatura do Capitão de Vanguarda.",
        resource_cost=3, target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id='empowered', duration=2), Effect(kind=EffectKind.APPLY_SHIELD, amount=2.0, scales_with=Stat.DEFENSE, scale_factor=0.5)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.34, Archetype.PATRULHEIRO: 0.33, Archetype.GUARDIAO: 0.33},
    ),
    "triple_runic_oath": Ability(
        id="triple_runic_oath", name="Juramento Rúnico",
        description="Um golpe arcano que também blinda quem o desfere -- a assinatura do Campeão Rúnico.",
        resource_cost=3, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.4, damage_element=DamageElement.ARCANE, poise_damage=3.0)],
        tags=["melee", "magic"], archetype_weight={Archetype.GUERREIRO: 0.34, Archetype.MISTICO: 0.33, Archetype.GUARDIAO: 0.33},
    ),
    "triple_arcane_watch": Ability(
        id="triple_arcane_watch", name="Vigília Arcana",
        description="Um disparo arcano que escuda o atirador -- a assinatura do Vigia Arcano.",
        resource_cost=3, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3, damage_element=DamageElement.ARCANE)],
        tags=["ranged", "magic"], archetype_weight={Archetype.PATRULHEIRO: 0.34, Archetype.MISTICO: 0.33, Archetype.GUARDIAO: 0.33},
    ),
    "errante_improvise": Ability(
        id="errante_improvise", name="Improviso",
        description="Um golpe de cada ofício, sem se prender a nenhum -- a assinatura do Errante do Wyrd.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2, random_damage_element=True)],
        tags=["melee", "ranged", "magic"], archetype_weight={Archetype.GUERREIRO: 0.25, Archetype.PATRULHEIRO: 0.25, Archetype.MISTICO: 0.25, Archetype.GUARDIAO: 0.25},
    ),
    "grey_path_step": Ability(
        id="grey_path_step", name="Passo Cinza",
        description="Equilíbrio em tudo: fere e cura na mesma medida -- a assinatura do Andarilho do Caminho Cinza.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0), Effect(kind=EffectKind.HEAL, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.5)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.25, Archetype.PATRULHEIRO: 0.25, Archetype.MISTICO: 0.25, Archetype.GUARDIAO: 0.25},
    ),
    "versatile_trick": Ability(
        id="versatile_trick", name="Mil Ofícios",
        description="A adaptabilidade humana num golpe que também recupera fôlego -- a assinatura do Andarilho Versátil.",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0), Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1.0)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.25, Archetype.PATRULHEIRO: 0.25, Archetype.MISTICO: 0.25, Archetype.GUARDIAO: 0.25},
    ),
    "justiceiro_judgment": Ability(
        id="justiceiro_judgment", name="Julgamento",
        description="Luz sagrada que pune o inimigo e ampara o grupo -- a assinatura do Justiceiro.",
        resource_cost=3, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.4, damage_element=DamageElement.HOLY, bonus_vs_tags=['undead', 'cursed'], bonus_vs_tags_bonus=0.5), Effect(kind=EffectKind.HEAL, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.4)],
        tags=["melee", "magic"], archetype_weight={Archetype.GUERREIRO: 0.6, Archetype.MISTICO: 0.4},
    ),
    "fae_flame": Ability(
        id="fae_flame", name="Fogo-Fátuo",
        description="Uma chama feérica caprichosa -- às vezes assusta, às vezes só queima -- a assinatura da Chama Feérica.",
        resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2, damage_element=DamageElement.ARCANE), Effect(kind=EffectKind.APPLY_STATUS, status_id='fear', duration=2, chance=0.5)],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "core_overdrive": Ability(
        id="core_overdrive", name="Núcleo Ativo",
        description="O núcleo sobrecarrega: escuda o próprio corpo e esmaga com Terra -- a assinatura do Núcleo de Batalha.",
        resource_cost=3, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.DEFENSE, scale_factor=1.5, damage_element=DamageElement.EARTH, poise_damage=5.0)],
        tags=["melee"], archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "juggernaut_unstoppable": Ability(
        id="juggernaut_unstoppable", name="Imparável",
        description="Nada segura o Juggernaut: atropela a linha inteira -- a assinatura de Estágio 2.",
        resource_cost=4, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.0, poise_damage=4.0)],
        tags=["melee", "cleave"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.GUARDIAO: 0.5},
    ),
    "colosso_world_weight": Ability(
        id="colosso_world_weight", name="Peso do Mundo",
        description="Um golpe com a massa de uma montanha -- a assinatura do Colosso de Estágio 2.",
        resource_cost=4, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=8.0, scales_with=Stat.DEFENSE, scale_factor=2.0, poise_damage=8.0)],
        tags=["melee"], archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    "berserker_bowstring_fury": Ability(
        id="berserker_bowstring_fury", name="Fúria de Corda",
        description="Flechas atiradas com a raiva de um Berserker -- a assinatura do Arqueiro-Berserker de Estágio 2.",
        resource_cost=3, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.0)],
        tags=["ranged"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.PATRULHEIRO: 0.5},
    ),
    # -- Habilidades Exclusivas de Arma (docs/design/10-sistemas-de-build.md
    # §3.4): granted by domain/weapons.py on equip, legal only while that
    # weapon is equipped, each weighted toward the weapon's natural
    # archetype -- the channel that lets Afinidade cross archetypes.
    "weapon_thrust": Ability(
        id="weapon_thrust", name="Estocada",
        description="Um golpe rápido de espada. (Espada de uma mão)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.2)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 1.0}, required_weapon_type="sword_one_hand",
    ),
    "weapon_cleave": Ability(
        id="weapon_cleave", name="Cutelada",
        description="Um arco largo que atinge todos os inimigos. (Espada grande)",
        resource_cost=2, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8, poise_damage=2.0)],
        tags=["melee", "cleave"], archetype_weight={Archetype.GUERREIRO: 1.0}, required_weapon_type="greatsword",
    ),
    "weapon_backstab": Ability(
        id="weapon_backstab", name="Punhalada",
        description="Um golpe traiçoeiro com alta chance de crítico. (Adaga)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0)],
        tags=["melee"], archetype_weight={Archetype.PATRULHEIRO: 1.0}, required_weapon_type="dagger",
    ),
    "weapon_charge": Ability(
        id="weapon_charge", name="Investida",
        description="Avança de lança em riste, abalando a postura. (Lança)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0, poise_damage=3.0)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.GUARDIAO: 0.5}, required_weapon_type="spear",
    ),
    "weapon_shot": Ability(
        id="weapon_shot", name="Disparo",
        description="Uma flecha certeira. (Arco)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1)],
        tags=["ranged"], archetype_weight={Archetype.PATRULHEIRO: 1.0}, required_weapon_type="bow",
    ),
    "weapon_fire": Ability(
        id="weapon_fire", name="Tiro",
        description="Um tiro seco e pesado. (Arma de fogo)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.0, poise_damage=2.0)],
        tags=["ranged"], archetype_weight={Archetype.PATRULHEIRO: 1.0}, required_weapon_type="firearm",
    ),
    "weapon_spark": Ability(
        id="weapon_spark", name="Faísca",
        description="Uma faísca arcana pela ponta do cajado. (Cajado)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.ARCANE)],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 1.0}, required_weapon_type="staff",
    ),
    "weapon_glyph": Ability(
        id="weapon_glyph", name="Glifo",
        description="Um glifo que fere todos os inimigos. (Grimório)",
        resource_cost=2, target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=0.7, damage_element=DamageElement.ARCANE)],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 1.0}, required_weapon_type="grimoire",
    ),
    "weapon_bash": Ability(
        id="weapon_bash", name="Golpe de Escudo",
        description="Bate com o escudo e se protege. (Escudo)",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.DEFENSE, scale_factor=1.0, poise_damage=3.0),
        ],
        tags=["melee"], archetype_weight={Archetype.GUARDIAO: 1.0}, required_weapon_type="shield",
    ),
    "weapon_punch": Ability(
        id="weapon_punch", name="Soco",
        description="Um soco seco, sem arma nenhuma. (Desarmado)",
        resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=0.9)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 0.5, Archetype.PATRULHEIRO: 0.5}, required_weapon_type="unarmed",
    ),
    # -- Tomos (docs/design/10-sistemas-de-build.md §3.8): taught by
    # domain/content/consumables.py's Tomos, one lesson per archetype.
    "tome_martial_blow": Ability(
        id="tome_martial_blow", name="Golpe Marcial",
        description="Um golpe de manual -- o básico do Guerreiro, aprendido no Tomo.",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1)],
        tags=["melee"], archetype_weight={Archetype.GUERREIRO: 1.0},
    ),
    "tome_ambush_shot": Ability(
        id="tome_ambush_shot", name="Tiro de Emboscada",
        description="Um disparo de posição -- o básico do Patrulheiro, aprendido no Tomo.",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1)],
        tags=["ranged"], archetype_weight={Archetype.PATRULHEIRO: 1.0},
    ),
    "tome_arcane_pulse": Ability(
        id="tome_arcane_pulse", name="Pulso Arcano",
        description="Um pulso de energia -- o básico do Místico, aprendido no Tomo.",
        resource_cost=1, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.ARCANE)],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 1.0},
    ),
    "tome_will_wall": Ability(
        id="tome_will_wall", name="Muro de Vontade",
        description="Um escudo de vontade sobre um aliado -- o básico do Guardião, aprendido no Tomo.",
        resource_cost=1, target_mode=TargetMode.SINGLE_ALLY,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=3.0, scales_with=Stat.DEFENSE, scale_factor=1.0)],
        tags=["melee"], archetype_weight={Archetype.GUARDIAO: 1.0},
    ),
    # -- Invocações (docs/design/11-habilidades.md §5 SUMMON, content in
    # domain/content/summons.py): what the summons themselves cast.
    "summon_spectral_touch": Ability(
        id="summon_spectral_touch", name="Toque Espectral",
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.SHADOW)],
        tags=["magic"],
    ),
    "summon_ink_smear": Ability(
        id="summon_ink_smear", name="Borrão de Tinta",
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=1.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.ARCANE)],
        tags=["magic"],
    ),
    "mad_copyist_draft": Ability(
        id="mad_copyist_draft", name="Rascunhar Cópia",
        description="Rabisca uma cópia tosca de si mesmo pra lutar ao seu lado.",
        resource_cost=0, target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.SUMMON, summon_id="copia_rascunhada")],
        tags=["magic"],
    ),
    # -- Renascido's "Abraçar a Morte" (04-racas.md; 09-roadmap.md decision 1):
    # below 15% PV, once per run -- immune to fatal damage for 1 turn, loses
    # 20% of max PV for the rest of the run, and raises the Medidor do Wyrd.
    # Universal (never a slot), granted by the race itself.
    "abracar_a_morte": Ability(
        id="abracar_a_morte", name="Abraçar a Morte",
        description="Abaixo de 15% de PV, uma vez por run: a morte espera 1 turno -- e leva 20% do PV máximo em troca.",
        resource_cost=0, target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.DEATH_WARD, amount=1.0, scale_factor=0.20)],
        universal=True, requires_hp_below=0.15, once_per_run=True, role="Utilidade",
    ),
    # -- Natureza Dual (04-racas.md Meio-celestial): universal, race-granted,
    # one switch per combat (Stat.EXTRA_USES_PER_COMBAT raises it).
    "assumir_forma_sagrada": Ability(
        id="assumir_forma_sagrada", name="Forma Sagrada",
        description="Assume a forma Sagrada: +40% de dano Sagrado, -20% de resistência a Sombrio, até o fim do combate.",
        resource_cost=0, target_mode=TargetMode.SELF, universal=True, uses_per_combat=1, role="Utilidade",
        effects=[Effect(kind=EffectKind.TRANSFORM, transform_id="forma_sagrada")],
    ),
    "assumir_forma_sombria": Ability(
        id="assumir_forma_sombria", name="Forma Sombria",
        description="Assume a forma Sombria: +40% de dano Sombrio, -20% de resistência a Sagrado, até o fim do combate.",
        resource_cost=0, target_mode=TargetMode.SELF, universal=True, uses_per_combat=1, role="Utilidade",
        effects=[Effect(kind=EffectKind.TRANSFORM, transform_id="forma_sombria")],
    ),
    "luz_e_sombra": Ability(
        id="luz_e_sombra", name="Luz e Sombra",
        description="Descarrega as duas naturezas de uma vez: dano Sagrado e Sombrio no mesmo alvo -- a assinatura do Avatar Dividido.",
        resource_cost=3, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8, damage_element=DamageElement.HOLY),
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.8, damage_element=DamageElement.SHADOW),
        ],
        tags=["magic"], archetype_weight={Archetype.MISTICO: 1.0},
    ),
    # -- Forma de Fera (content/transforms.py): the Licantropo's transformed
    # kit. No archetype_weight: a form's instincts aren't a career choice.
    "fera_dilacerar": Ability(
        id="fera_dilacerar", name="Dilacerar",
        description="Garras que rasgam: dano físico alto e Sangrando.",
        resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.3, poise_damage=4.0),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="bleeding", duration=3),
        ],
        tags=["melee"], role="Dano",
    ),
    "fera_mordida_voraz": Ability(
        id="fera_mordida_voraz", name="Mordida Voraz",
        description="Morde e devora: dano físico pesado que quebra a postura (a Forma de Fera rouba vida em todo golpe).",
        resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.1, poise_damage=6.0)],
        tags=["melee"], role="Dano",
    ),
    "fera_uivo": Ability(
        id="fera_uivo", name="Uivo",
        description="Um uivo que amedronta todos os inimigos por 2 turnos.",
        resource_cost=0, target_mode=TargetMode.ALL_ENEMIES, cooldown_turns=3,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="fear", duration=2)],
        tags=["melee"], role="Controle",
    ),
    # -- Companheiros (Fase 9, domain/companions.py): no archetype_weight
    # on purpose -- a companion's actions never feed its owner's Afinidade.
    "companion_bite": Ability(
        id="companion_bite",
        name="Mordida",
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0, poise_damage=1.0)],
        tags=["melee"],
    ),
    "companion_peck": Ability(
        id="companion_peck",
        name="Bicada",
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=1.0, scales_with=Stat.ATTACK, scale_factor=0.8),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="weakened", duration=2),
            # the Corvo marks its prey for its owner (Combo em Equipe)
            Effect(kind=EffectKind.APPLY_STATUS, status_id="marcado_para_combo", duration=2),
        ],
        tags=["ranged"],
    ),
    "companion_ember": Ability(
        id="companion_ember",
        name="Brasa",
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0, damage_element=DamageElement.FIRE),
        ],
        tags=["ranged"],
    ),
    "companion_shell": Ability(
        id="companion_shell",
        name="Casco",
        target_mode=TargetMode.SINGLE_ALLY,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=3.0, scales_with=Stat.DEFENSE, scale_factor=1.0)],
        tags=["melee"],
    ),
    # -- Cartas de habilidade ativa (Fase 7, docs/design/10-sistemas-de-build.md
    # §3.7). Universal -- no archetype_weight, so they don't shift Afinidade.
    "card_second_wind": Ability(
        id="card_second_wind",
        name="Segundo Fôlego",
        description="Recupera o fôlego e um pouco de PV.",
        resource_cost=2,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.HEAL, amount=6.0, scales_with=Stat.MAX_HP, scale_factor=0.1)],
    ),
    "card_flame_lash": Ability(
        id="card_flame_lash",
        name="Chicote de Chamas",
        description="Um chicote de fogo num único alvo.",
        resource_cost=2,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.4,
                damage_element=DamageElement.FIRE,
            )
        ],
        tags=["magic"],
    ),
    "card_arcane_flare": Ability(
        id="card_arcane_flare",
        name="Fulgor Arcano",
        description="Energia arcana contra todos os inimigos.",
        resource_cost=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.9,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
    ),
    # -- Enemy kit -----------------------------------------------------------
    "goblin_bite": Ability(
        id="goblin_bite",
        name="Bite",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=1.0, scales_with=Stat.ATTACK, scale_factor=1.0)],
        tags=["melee"],
    ),
    "skitter_bite": Ability(
        id="skitter_bite",
        name="Venomous Bite",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=1.0, scales_with=Stat.ATTACK, scale_factor=1.0),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1),
        ],
        tags=["melee"],
    ),
    "bonewarden_slam": Ability(
        id="bonewarden_slam",
        name="Bone Slam",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.1)],
        tags=["melee"],
    ),
    "hollow_smite": Ability(
        id="hollow_smite",
        name="Hollow Smite",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.3)],
        tags=["melee"],
    ),
    "hollow_cleave": Ability(
        id="hollow_cleave",
        name="Hollow Cleave",
        description="Atinge todos os heróis de uma vez.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=0.6)],
        tags=["melee"],
    ),
    "hollow_cleave_bleed": Ability(
        id="hollow_cleave_bleed",
        name="Fúria do Guardião",
        description="Um cleave mais selvagem que deixa os alvos Sangrando -- a fase final do Cavaleiro Oco.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=0.6),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="bleeding", duration=3, stacks=1),
        ],
        tags=["melee"],
    ),
    # -- Área 2: As Fornalhas Vivas (Fogo) -------------------------------------
    "ember_bolt": Ability(
        id="ember_bolt",
        name="Ember Bolt",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.FIRE,
            )
        ],
        tags=["magic"],
    ),
    "forge_slam": Ability(
        id="forge_slam",
        name="Forge Slam",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2)],
        tags=["melee"],
    ),
    "bellows_empower": Ability(
        id="bellows_empower",
        name="Bellows Roar",
        description="Aplica Fortalecido em todos os aliados próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="empowered", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "magma_golem_charge": Ability(
        id="magma_golem_charge",
        name="Investida de Magma",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.2)],
        tags=["melee"],
    ),
    "magma_golem_eruption": Ability(
        id="magma_golem_eruption",
        name="Erupção",
        description="Dano de Fogo em área.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=0.5,
                damage_element=DamageElement.FIRE,
            )
        ],
        tags=["magic"],
    ),
    "ashkarion_smash": Ability(
        id="ashkarion_smash",
        name="Golpe da Forja",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3)],
        tags=["melee"],
    ),
    "ashkarion_eruption": Ability(
        id="ashkarion_eruption",
        name="Forja Aberta",
        description="A câmara inteira arde em Fogo.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.6,
                damage_element=DamageElement.FIRE,
            )
        ],
        tags=["magic"],
    ),
    "ashkarion_frenzy": Ability(
        id="ashkarion_frenzy",
        name="Fúria do Magma",
        description="Um golpe desesperado e mais rápido -- a última cartada de Ashkarion.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.5)],
        tags=["melee"],
    ),
    # -- Área 3: O Pico Silente (Gelo) ------------------------------------------
    "wolf_bite": Ability(
        id="wolf_bite",
        name="Mordida Gélida",
        description="Aplica Lentidão no acerto.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="lentidao", duration=2, stacks=1),
        ],
        tags=["melee"],
    ),
    "frost_touch": Ability(
        id="frost_touch",
        name="Toque Gélido",
        description="Empilha Fragilidade ao Gelo no alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ICE,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="fragilidade_ao_gelo", duration=3, stacks=1),
        ],
        tags=["magic"],
    ),
    "ice_ward": Ability(
        id="ice_ward",
        name="Barreira de Gelo",
        description="Aplica um escudo de gelo em todos os aliados próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_SHIELD, amount=6.0, scales_with=Stat.DEFENSE, scale_factor=1.2)],
        tags=["magic"],
    ),
    "icicle_volley": Ability(
        id="icicle_volley",
        name="Rajada de Carâmbanos",
        description="Aplica Fragilidade ao Gelo diretamente, sem precisar empilhar aos poucos.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.ICE,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="fragilidade_ao_gelo", duration=3, stacks=2),
        ],
        tags=["ranged"],
    ),
    "viuva_frost_bolt": Ability(
        id="viuva_frost_bolt",
        name="Farpa de Gelo",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ICE,
            )
        ],
        tags=["ranged"],
    ),
    "viuva_ice_lance": Ability(
        id="viuva_ice_lance",
        name="Lança de Gelo",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.ICE, poise_damage=4.0,
            )
        ],
        tags=["melee"],
    ),
    "viuva_glacial_shatter": Ability(
        id="viuva_glacial_shatter",
        name="Estilhaço Glacial",
        description="O golpe mais forte da Viúva de Gelo, guardado para a Ventania Final.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.4,
                damage_element=DamageElement.ICE,
            )
        ],
        tags=["ranged"],
    ),
    # -- Área 4: A Tempestade Eterna (Raio) --------------------------------------
    "thunderbird_strike": Ability(
        id="thunderbird_strike",
        name="Investida do Trovão",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.LIGHTNING, chain_percent=0.5,
            )
        ],
        tags=["ranged"],
    ),
    "sentinela_shock": Ability(
        id="sentinela_shock",
        name="Choque da Sentinela",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.LIGHTNING, poise_damage=3.0,
            )
        ],
        tags=["melee"],
    ),
    "storm_bolt": Ability(
        id="storm_bolt",
        name="Raio da Tempestade",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.LIGHTNING, chain_percent=0.5,
            )
        ],
        tags=["magic"],
    ),
    "storm_haste": Ability(
        id="storm_haste",
        name="Aceleração da Tempestade",
        description="Aplica Acelerado em todos os aliados próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="acelerado", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "charged_bolt": Ability(
        id="charged_bolt",
        name="Descarga Carregada",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.LIGHTNING, chain_percent=0.5,
            )
        ],
        tags=["ranged"],
    ),
    "charged_burst": Ability(
        id="charged_burst",
        name="Liberação de Carga",
        description="A carga acumulada se libera em área.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=0.6,
                damage_element=DamageElement.LIGHTNING,
            )
        ],
        tags=["magic"],
    ),
    "voltharion_bolt": Ability(
        id="voltharion_bolt",
        name="Raio de Voltharion",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.LIGHTNING, chain_percent=0.5,
            )
        ],
        tags=["ranged"],
    ),
    "voltharion_strike": Ability(
        id="voltharion_strike",
        name="Golpe da Tempestade",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3,
                damage_element=DamageElement.LIGHTNING, poise_damage=5.0,
            )
        ],
        tags=["melee"],
    ),
    "voltharion_tempest": Ability(
        id="voltharion_tempest",
        name="Tempestade Final",
        description="Encadeia entre todos os jogadores vivos -- o golpe de assinatura de Voltharion.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.8,
                damage_element=DamageElement.LIGHTNING,
            )
        ],
        tags=["magic"],
    ),
    # -- Área 5: As Profundezas Afogadas (Água) ----------------------------------
    "drowned_grasp": Ability(
        id="drowned_grasp",
        name="Garra Afogada",
        description="Aplica Encharcado no acerto.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.WATER,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="encharcado", duration=3, stacks=1),
        ],
        tags=["melee"],
    ),
    "resource_drain": Ability(
        id="resource_drain",
        name="Sugar Vontade",
        description="Rouba Resolução do alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DRAIN_RESOURCE, amount=2.0)],
        tags=["magic"],
    ),
    "drowned_blessing": Ability(
        id="drowned_blessing",
        name="Bênção Afogada",
        description="Cura todos os aliados próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.HEAL, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.5)],
        tags=["magic"],
    ),
    "kraken_tentacle_strike": Ability(
        id="kraken_tentacle_strike",
        name="Golpe de Tentáculo",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.WATER, poise_damage=3.0,
            )
        ],
        tags=["melee"],
    ),
    "kraken_crush": Ability(
        id="kraken_crush",
        name="Esmagamento",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3,
                damage_element=DamageElement.WATER,
            )
        ],
        tags=["melee"],
    ),
    "kraken_soak": Ability(
        id="kraken_soak",
        name="Encharcar",
        description="Aplica Encharcado em todos os inimigos próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="encharcado", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "maremoto_bite": Ability(
        id="maremoto_bite",
        name="Mordida das Profundezas",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.WATER,
            )
        ],
        tags=["melee"],
    ),
    "maremoto_soak": Ability(
        id="maremoto_soak",
        name="Correntes Profundas",
        description="Aplica Encharcado em todos os inimigos próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="encharcado", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "maremoto_undertow": Ability(
        id="maremoto_undertow",
        name="Correnteza Submersa",
        description="Aplica Correnteza (Lentidão pesada) no acerto -- a Fúria da Maré.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.WATER,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="correnteza", duration=2, stacks=1),
        ],
        tags=["melee"],
    ),
    # -- Área 6: As Minas Esquecidas (Terra) -------------------------------------
    "stoneworm_ambush": Ability(
        id="stoneworm_ambush",
        name="Emboscada de Pedra",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.EARTH,
            )
        ],
        tags=["melee"],
    ),
    "gravel_slam": Ability(
        id="gravel_slam",
        name="Golpe de Cascalho",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.EARTH,
            )
        ],
        tags=["melee"],
    ),
    "shatter_curse": Ability(
        id="shatter_curse",
        name="Maldição Fragmentadora",
        description="Aplica Fragmentado no alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="fragmentado", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "crystal_guard_strike": Ability(
        id="crystal_guard_strike",
        name="Golpe Cristalino",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.EARTH, poise_damage=3.0,
            )
        ],
        tags=["melee"],
    ),
    "terrakon_crush": Ability(
        id="terrakon_crush",
        name="Esmagamento da Montanha",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.EARTH, poise_damage=4.0,
            )
        ],
        tags=["melee"],
    ),
    "terrakon_quake": Ability(
        id="terrakon_quake",
        name="Tremor",
        description="Um tremor atinge todos os heróis de uma vez.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.7,
                damage_element=DamageElement.EARTH,
            )
        ],
        tags=["melee"],
    ),
    # -- Área 7: Os Pináculos Flutuantes (Ar) ------------------------------------
    "harpy_gust": Ability(
        id="harpy_gust",
        name="Rajada da Harpia",
        description="Aplica Desequilibrado no acerto.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.AIR,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="desequilibrado", duration=3, stacks=1),
        ],
        tags=["ranged"],
    ),
    "wind_gale": Ability(
        id="wind_gale",
        name="Rajada de Vento",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.AIR,
            )
        ],
        tags=["magic"],
    ),
    "gale_call": Ability(
        id="gale_call",
        name="Chamado do Vendaval",
        description="Reduz a Iniciativa de todos os heróis próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="lentidao", duration=2, stacks=1)],
        tags=["magic"],
    ),
    "roc_strike": Ability(
        id="roc_strike",
        name="Golpe do Roc",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.AIR, poise_damage=3.0,
            )
        ],
        tags=["melee"],
    ),
    "zephyra_gust": Ability(
        id="zephyra_gust",
        name="Rajada de Zephyra",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.AIR,
            )
        ],
        tags=["ranged"],
    ),
    "zephyra_double_gale": Ability(
        id="zephyra_double_gale",
        name="Vendaval Duplo",
        description="Dois golpes de vento no mesmo alvo -- Zephyra ficou mais rápida.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.AIR,
            ),
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.AIR,
            ),
        ],
        tags=["ranged"],
    ),
    # -- Área 8: O Pântano Pútrido (Veneno) --------------------------------------
    "leech_bite": Ability(
        id="leech_bite",
        name="Mordida da Sanguessuga",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.POISON,
            )
        ],
        tags=["melee"],
    ),
    "spore_bolt": Ability(
        id="spore_bolt",
        name="Esporo Venenoso",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.POISON,
            )
        ],
        tags=["magic"],
    ),
    "mud_curse": Ability(
        id="mud_curse",
        name="Maldição do Lodo",
        description="Empilha Veneno rapidamente no alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=2)],
        tags=["magic"],
    ),
    "bog_horror_strike": Ability(
        id="bog_horror_strike",
        name="Golpe do Horror do Charco",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.POISON,
            )
        ],
        tags=["melee"],
    ),
    "putrid_mother_bite": Ability(
        id="putrid_mother_bite",
        name="Mordida Pútrida",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.POISON, poise_damage=3.0,
            )
        ],
        tags=["melee"],
    ),
    "putrid_cloud": Ability(
        id="putrid_cloud",
        name="Nuvem Pútrida",
        description="Uma nuvem de esporos aplica Veneno em todos os heróis.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "putrid_swarm": Ability(
        id="putrid_swarm",
        name="Enxame Pútrido",
        description="A fase mais intensa da Mãe Pútrida -- dano e Veneno em todos os heróis.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=0.6,
                damage_element=DamageElement.POISON,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1),
        ],
        tags=["magic"],
    ),
    # -- Área 9: O Santuário Desmoronado (Sagrado) -------------------------------
    "seraph_strike": Ability(
        id="seraph_strike",
        name="Golpe do Serafim",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.HOLY,
            )
        ],
        tags=["magic"],
    ),
    "seraph_mend": Ability(
        id="seraph_mend",
        name="Restauração do Serafim",
        description="Cura a si mesmo.",
        resource_cost=0,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.HEAL, amount=5.0, scales_with=Stat.ATTACK, scale_factor=0.5)],
        tags=["magic"],
    ),
    "zealot_strike": Ability(
        id="zealot_strike",
        name="Golpe do Zelote",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.HOLY,
            )
        ],
        tags=["melee"],
    ),
    "zealot_fury_strike": Ability(
        id="zealot_fury_strike",
        name="Fúria Cega",
        description="Quanto mais baixo o próprio PV, mais forte -- a fase final do Zelote Cego.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.4,
                damage_element=DamageElement.HOLY,
            )
        ],
        tags=["melee"],
    ),
    "hymn_curse": Ability(
        id="hymn_curse",
        name="Hino da Maldição",
        description="Aplica Amaldiçoado no alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="amaldicoado", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "light_guardian_strike": Ability(
        id="light_guardian_strike",
        name="Golpe do Guardião de Luz",
        description="Causa dano bônus contra criaturas mortas-vivas ou amaldiçoadas.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.HOLY, poise_damage=3.0,
                bonus_vs_tags=["undead", "cursed"], bonus_vs_tags_bonus=0.5,
            )
        ],
        tags=["melee"],
    ),
    "solyth_mercy": Ability(
        id="solyth_mercy",
        name="Piedade de Solyth",
        description="Cura o grupo de heróis, sem querer -- a fase inicial de Solyth.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.HEAL, amount=4.0, scales_with=Stat.ATTACK, scale_factor=0.4)],
        tags=["magic"],
    ),
    "solyth_smite": Ability(
        id="solyth_smite",
        name="Julgamento de Solyth",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.HOLY,
            )
        ],
        tags=["magic"],
    ),
    "solyth_fallen_wrath": Ability(
        id="solyth_fallen_wrath",
        name="Ira do Anjo Caído",
        description="A fase final de Solyth -- causa dano bônus contra mortos-vivos e amaldiçoados.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.4,
                damage_element=DamageElement.HOLY,
                bonus_vs_tags=["undead", "cursed"], bonus_vs_tags_bonus=0.5,
            )
        ],
        tags=["magic"],
    ),
    # -- Área 10: A Sombra Sob o Véu (Sombrio) -----------------------------------
    "whisper_fear": Ability(
        id="whisper_fear",
        name="Sussurro do Medo",
        description="Aplica Medo no alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=2.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.SHADOW,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="fear", duration=3, stacks=1),
        ],
        tags=["magic"],
    ),
    "cursed_flesh_strike": Ability(
        id="cursed_flesh_strike",
        name="Golpe da Carne Amaldiçoada",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.SHADOW,
            )
        ],
        tags=["melee"],
    ),
    "veil_herald_ward": Ability(
        id="veil_herald_ward",
        name="Manto do Véu",
        description="Aumenta a Esquiva de todos os aliados próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="esquiva_sombria", duration=3, stacks=1)],
        tags=["magic"],
    ),
    "light_devourer_drain": Ability(
        id="light_devourer_drain",
        name="Sugar Luz",
        description="Drena Resolução de todo o grupo de heróis.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DRAIN_RESOURCE, amount=2.0)],
        tags=["magic"],
    ),
    "nameless_claws": Ability(
        id="nameless_claws",
        name="Máscara de Garras",
        description="Um golpe rápido e brutal.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.3,
                damage_element=DamageElement.SHADOW,
            )
        ],
        tags=["melee"],
    ),
    "nameless_eyes": Ability(
        id="nameless_eyes",
        name="Máscara de Olhos",
        description="Um olhar à distância que aplica Medo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.SHADOW,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="fear", duration=3, stacks=1),
        ],
        tags=["ranged"],
    ),
    "nameless_mouths": Ability(
        id="nameless_mouths",
        name="Máscara de Bocas",
        description="Bocas famintas drenam Resolução de todo o grupo.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.DRAIN_RESOURCE, amount=3.0)],
        tags=["magic"],
    ),
    # -- Área 11: A Biblioteca Fraturada (Arcano) ---------------------------------
    "wandering_book_read": Ability(
        id="wandering_book_read",
        name="Página Cortante",
        description="Um golpe de dano arcano que ignora parte da resistência do alvo.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.ARCANE, resist_penetration_percent=0.5,
            )
        ],
        tags=["magic"],
    ),
    # Eco Arcano: 3 abilities styled after 3 different archetypes so that
    # resolve_ai_turn's existing uniform-random ability pick (combat.py's
    # `self.rng.choice(candidates)`, true every turn for every enemy)
    # already delivers "usa uma habilidade genérica de arquétipo aleatório
    # a cada turno" with zero new engine work.
    "arcane_echo_strike": Ability(
        id="arcane_echo_strike",
        name="Investida Ecoante",
        description="Um golpe físico brusco, como um guerreiro.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.2)],
        tags=["melee"],
    ),
    "arcane_echo_bolt": Ability(
        id="arcane_echo_bolt",
        name="Raio Instável",
        description="Um raio de energia de elemento imprevisível, como um mago.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                random_damage_element=True,
            )
        ],
        tags=["magic"],
    ),
    "arcane_echo_focus": Ability(
        id="arcane_echo_focus",
        name="Foco Ecoante",
        description="Concentra energia arcana, como um suporte.",
        resource_cost=0,
        target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="empowered", duration=2, stacks=1)],
        tags=["magic"],
    ),
    # Copista Louco: doc mecânica "replica o último efeito que o grupo de
    # jogadores usou, devolvendo contra eles" needs a last-player-action
    # history that CombatState doesn't track. Disclosed simplification
    # (Fase 7 increment 10 plan): applies the existing "weakened" debuff
    # to the whole party instead of a dynamic mirror.
    "mad_copyist_mirror": Ability(
        id="mad_copyist_mirror",
        name="Espelho Distorcido",
        description="Tenta espelhar o grupo de heróis e devolve a distorção contra eles.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="weakened", duration=2, stacks=1)],
        tags=["magic"],
    ),
    "mad_copyist_silence": Ability(
        id="mad_copyist_silence",
        name="Silenciar",
        description="Rasura as palavras do alvo -- sem magia por 2 turnos.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="silencio", duration=2)],
        tags=["magic"],
        role="Controle",
    ),
    # Paradoxo Ambulante: doc's own defining identity for this Elite --
    # "elemento de dano aleatório a cada turno", built for real via
    # random_damage_element (no per-turn RNG hackery needed beyond the
    # engine field itself).
    "paradox_unstable_strike": Ability(
        id="paradox_unstable_strike",
        name="Golpe Instável",
        description="Um golpe cujo elemento muda a cada investida.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                random_damage_element=True,
            )
        ],
        tags=["magic"],
    ),
    "paradox_arcane_rift": Ability(
        id="paradox_arcane_rift",
        name="Fenda Arcana",
        description="Uma fenda de energia pura que ignora boa parte de qualquer resistência.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ARCANE, resist_penetration_percent=0.6,
            )
        ],
        tags=["magic"],
    ),
    "nyxelle_shredded_page": Ability(
        id="nyxelle_shredded_page",
        name="Página Rasgada",
        description="Um corte de páginas fraturadas, imbuído de energia arcana.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
    ),
    "nyxelle_unbound_knowledge": Ability(
        id="nyxelle_unbound_knowledge",
        name="Conhecimento Desamarrado",
        description="Um golpe de elemento instável, herdado dos próprios Ecos.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=5.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                random_damage_element=True,
            )
        ],
        tags=["magic"],
    ),
    "echo_of_fire": Ability(
        id="echo_of_fire",
        name="Eco de Fogo",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.1,
                damage_element=DamageElement.FIRE,
            )
        ],
        tags=["magic"],
    ),
    "echo_of_ice": Ability(
        id="echo_of_ice",
        name="Eco de Gelo",
        description="Um sopro gelado que fragiliza contra o próprio frio.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=3.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ICE,
            ),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="fragilidade_ao_gelo", duration=3, stacks=1),
        ],
        tags=["magic"],
    ),
    # -- Área 12: O Tear Desfeito (final, todos os elementos) --------------------
    # Sombra de Arquétipo: doc mecânica "copia o Arquétipo Base de um
    # jogador específico" needs a way to read a specific player's build
    # and mirror it, which doesn't exist. Disclosed simplification (Fase
    # 7 increment 11 plan): a static melee+magic hybrid instead.
    "archetype_shadow_slash": Ability(
        id="archetype_shadow_slash",
        name="Golpe do Destino Roubado",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.2)],
        tags=["melee"],
    ),
    "archetype_shadow_bolt": Ability(
        id="archetype_shadow_bolt",
        name="Eco do Destino Roubado",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=4.0, scales_with=Stat.ATTACK, scale_factor=1.0,
                damage_element=DamageElement.ARCANE,
            )
        ],
        tags=["magic"],
    ),
    # Fiandeira Menor: doc mecânica "acelera o Medidor do Wyrd de todos
    # os presentes" needs a system that's explicitly Fase 8 scope
    # (09-roadmap.md), not built yet. Disclosed simplification: a
    # generic ally-attack buff instead.
    "spinner_hasten": Ability(
        id="spinner_hasten",
        name="Fiar o Ritmo",
        description="Acelera o ritmo dos aliados próximos.",
        resource_cost=0,
        target_mode=TargetMode.ALL_ALLIES,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="empowered", duration=2, stacks=1)],
        tags=["magic"],
    ),
    "loom_thread_of_fire": Ability(
        id="loom_thread_of_fire",
        name="Fio de Fogo",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.FIRE,
            )
        ],
        tags=["magic"],
    ),
    "loom_thread_of_ice": Ability(
        id="loom_thread_of_ice",
        name="Fio de Gelo",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.0, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.ICE,
            )
        ],
        tags=["magic"],
    ),
    "loom_thread_of_lightning": Ability(
        id="loom_thread_of_lightning",
        name="Fio de Raio",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.5, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.LIGHTNING,
            )
        ],
        tags=["magic"],
    ),
    "loom_thread_of_earth": Ability(
        id="loom_thread_of_earth",
        name="Fio de Terra",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=6.5, scales_with=Stat.ATTACK, scale_factor=1.2,
                damage_element=DamageElement.EARTH,
            )
        ],
        tags=["melee"],
    ),
    "loom_thread_of_shadow": Ability(
        id="loom_thread_of_shadow",
        name="Fio de Sombra",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=7.0, scales_with=Stat.ATTACK, scale_factor=1.3,
                damage_element=DamageElement.SHADOW,
            )
        ],
        tags=["magic"],
    ),
    "loom_thread_of_light": Ability(
        id="loom_thread_of_light",
        name="Fio de Luz",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE, amount=7.0, scales_with=Stat.ATTACK, scale_factor=1.3,
                damage_element=DamageElement.HOLY,
            )
        ],
        tags=["magic"],
    ),
    "loom_broken_thread": Ability(
        id="loom_broken_thread",
        name="Fio Partido",
        description="Um golpe bruto, sem elemento fixo -- só força.",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=8.0, scales_with=Stat.ATTACK, scale_factor=1.4)],
        tags=["melee"],
    ),
}

from wyrdfall.domain.card_catalog import CARD_ABILITIES

ABILITY_DEFS.update(CARD_ABILITIES)
