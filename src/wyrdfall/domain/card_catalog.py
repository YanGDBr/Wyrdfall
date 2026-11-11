"""Authored card expansion: tradeoffs, reactive builds and twelve active techniques."""
from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.items import Rarity
from wyrdfall.domain.models import (
    Archetype, DamageElement, Effect, EffectKind, Modifier, ModifierKind,
    Stat, TriggerEvent, TriggeredEffect,
)


def _damage(amount, element=DamageElement.PHYSICAL, scale=0.4, **kwargs):
    return Effect(kind=EffectKind.DAMAGE, amount=amount, scales_with=Stat.ATTACK,
                  scale_factor=scale, damage_element=element, **kwargs)


def _status(status, turns=2):
    return Effect(kind=EffectKind.APPLY_STATUS, status_id=status, duration=turns)


def _ability(id, name, target, effects, cost=2, archetype=Archetype.MISTICO, **kwargs):
    return Ability(id=id, name=name, resource_cost=cost, target_mode=target, effects=effects,
                   archetype_weight={archetype: 1.0}, tags=["magic"], **kwargs)


CARD_ABILITIES = {a.id: a for a in [
    _ability("card_agulha_glacial", "Agulha Glacial", TargetMode.SINGLE_ENEMY,
             [_damage(3, DamageElement.ICE), _status("lentidao")]),
    _ability("card_trovoada", "Trovoada de Bolso", TargetMode.ALL_ENEMIES,
             [_damage(2, DamageElement.LIGHTNING, 0.25)], cost=3, cooldown_turns=2),
    _ability("card_beijo_vibora", "Beijo da Víbora", TargetMode.SINGLE_ENEMY,
             [_damage(2, DamageElement.POISON), _status("poisoned", 3)], archetype=Archetype.PATRULHEIRO),
    _ability("card_agua_benta", "Água de Recomeço", TargetMode.SINGLE_ALLY,
             [Effect(kind=EffectKind.HEAL, amount=6), Effect(kind=EffectKind.CLEANSE, amount=1)],
             archetype=Archetype.GUARDIAO, cooldown_turns=2),
    _ability("card_muralha", "Muralha de Bolso", TargetMode.ALL_ALLIES,
             [Effect(kind=EffectKind.APPLY_SHIELD, amount=5)], cost=3,
             archetype=Archetype.GUARDIAO, cooldown_turns=3),
    _ability("card_empurrao", "Rajada Desalinhada", TargetMode.SINGLE_ENEMY,
             [_damage(3, DamageElement.AIR), _status("desequilibrado")]),
    _ability("card_reacender", "Reacender a Centelha", TargetMode.SINGLE_ALLY,
             [Effect(kind=EffectKind.REVIVE, amount=0.25)], cost=3,
             archetype=Archetype.GUARDIAO, uses_per_combat=1),
    _ability("card_roubo_sombras", "Empréstimo das Sombras", TargetMode.SINGLE_ENEMY,
             [_damage(2, DamageElement.SHADOW), Effect(kind=EffectKind.DRAIN_RESOURCE, amount=2)],
             cooldown_turns=2),
    _ability("card_martelo_terra", "Martelo de Barro", TargetMode.SINGLE_ENEMY,
             [_damage(3, DamageElement.EARTH, 0.5, poise_damage=5)], archetype=Archetype.GUERREIRO),
    _ability("card_onda", "Onda de Vidro", TargetMode.ALL_ENEMIES,
             [_damage(1, DamageElement.WATER, 0.25), _status("encharcado", 1)], cost=3, cooldown_turns=2),
    _ability("card_sinal_cacada", "Sinal da Caçada", TargetMode.SINGLE_ENEMY,
             [_status("marked"), _status("marcado_para_combo")], cost=1,
             archetype=Archetype.PATRULHEIRO, cooldown_turns=2),
    _ability("card_voto_sangue", "Voto de Sangue", TargetMode.SELF,
             [_status("empowered", 3)], cost=0.1, archetype=Archetype.GUERREIRO,
             pays_with_hp=True, cooldown_turns=3),
]}


def build_extra_cards(card_type):
    cards = {}

    def passive(id, name, rarity, description, *mods):
        cards[id] = card_type(id=id, name=name, rarity=rarity, description=description,
            modifiers=[Modifier(stat=stat, kind=kind, value=value, source=f"card_{id}")
                       for stat, kind, value in mods])

    def reactive(id, name, rarity, description, trigger, effect, target="self", chance=1.0):
        cards[id] = card_type(id=id, name=name, rarity=rarity, description=description,
            damage_elements={DamageElement.POISON} if effect.status_id == "poisoned" else set(),
            triggered_effects=[TriggeredEffect(trigger=trigger, effect=effect, applies_to=target,
                                              chance=chance, source=f"card_{id}")])

    F, P, M = ModifierKind.FLAT, ModifierKind.PERCENT, ModifierKind.MORE
    C, R, L = Rarity.COMUM, Rarity.RARO, Rarity.LENDARIO
    # Nineteen common cards: small specializations and readable tradeoffs.
    passive("pedra_paciente", "Pedra Paciente", C, "+2 Defesa; -1 Velocidade.", (Stat.DEFENSE,F,2), (Stat.SPEED,F,-1))
    passive("bolso_fundo", "Bolso sem Fundo", C, "+2 de recurso máximo.", (Stat.MAX_RESOURCE,F,2))
    passive("bota_mensageiro", "Passos do Mensageiro", C, "+1 Velocidade e +3 PV máximos.", (Stat.SPEED,F,1), (Stat.MAX_HP,F,3))
    passive("agulha_aco", "Agulha de Aço", C, "+8% de penetração de armadura.", (Stat.ARMOR_PENETRATION_PERCENT,F,.08))
    passive("sal_protetor", "Sal do Limiar", C, "+8% de resistência a status.", (Stat.STATUS_RESIST,F,.08))
    passive("pulseira_nascente", "Pulseira da Nascente", C, "+12% de cura recebida.", (Stat.HEALING_RECEIVED_PERCENT,F,.12))
    passive("luvas_socorrista", "Luvas do Socorrista", C, "+10% de cura realizada.", (Stat.HEALING_DONE_PERCENT,F,.10))
    passive("escama_morna", "Escama Morna", C, "+12% resistência a Fogo.", (Stat.FIRE_RESIST,F,.12))
    passive("cachecol_inverno", "Cachecol do Inverno", C, "+12% resistência a Gelo.", (Stat.ICE_RESIST,F,.12))
    passive("raiz_amarga", "Raiz Amarga", C, "+12% resistência a Veneno.", (Stat.POISON_RESIST,F,.12))
    passive("fio_terra", "Fio-Terra", C, "+12% resistência a Raio.", (Stat.LIGHTNING_RESIST,F,.12))
    passive("vela_vigia", "Vela do Vigia", C, "+12% resistência a Sombra.", (Stat.SHADOW_RESIST,F,.12))
    passive("olho_vidro", "Olho de Vidro", C, "+3% Crítico e +10% multiplicador crítico.", (Stat.CRIT_CHANCE,F,.03), (Stat.CRIT_MULT,F,.10))
    passive("casca_oca", "Casca Oca", C, "+8 PV máximos; -1 Ataque.", (Stat.MAX_HP,F,8), (Stat.ATTACK,F,-1))
    passive("punho_leve", "Punho Leve", C, "+3 Ataque; -1 Defesa.", (Stat.ATTACK,F,3), (Stat.DEFENSE,F,-1))
    passive("cota_remendada", "Cota Remendada", C, "+5% Bloqueio e +1 Defesa.", (Stat.BLOCK_CHANCE,F,.05), (Stat.DEFENSE,F,1))
    passive("respiracao_longa", "Respiração Longa", C, "+0,3 recurso por turno e +1 recurso máximo.", (Stat.RESOURCE_REGEN_PER_TURN,F,.3), (Stat.MAX_RESOURCE,F,1))
    passive("lamina_equilibrada", "Lâmina Equilibrada", C, "+6% de dano Físico.", (Stat.PHYSICAL_DAMAGE_PERCENT,F,.06))
    passive("bussola_arcana", "Bússola Arcana", C, "+6% dano elemental; -1 PV máximo.", (Stat.ELEMENTAL_DAMAGE_PERCENT,F,.06), (Stat.MAX_HP,F,-1))

    # Twenty rares: coherent reactive engines and bolder exchanges.
    passive("coroa_ervas", "Coroa de Ervas", R, "+18% cura realizada; +8% resistência a status.", (Stat.HEALING_DONE_PERCENT,F,.18), (Stat.STATUS_RESIST,F,.08))
    passive("coracao_musgo", "Coração de Musgo", R, "+18% PV máximos; -1 Velocidade.", (Stat.MAX_HP,P,.18), (Stat.SPEED,F,-1))
    passive("nucleo_vazio", "Núcleo Vazio", R, "+4 recurso máximo; -10% PV máximos.", (Stat.MAX_RESOURCE,F,4), (Stat.MAX_HP,P,-.10))
    passive("voto_ferro", "Voto de Ferro", R, "+20% eficiência de Bloqueio.", (Stat.BLOCK_PERCENT,F,.20))
    passive("espelho_fosco", "Espelho Fosco", R, "+10% resistência a Crítico e +5% resistência elemental geral.", (Stat.CRIT_RESIST,F,.10), (Stat.GENERAL_ELEMENTAL_RESIST,F,.05))
    passive("fenda_armadura", "Mapa das Fendas", R, "+18% penetração de armadura; -1 Defesa.", (Stat.ARMOR_PENETRATION_PERCENT,F,.18), (Stat.DEFENSE,F,-1))
    passive("foco_instavel", "Foco Instável", R, "+18% dano elemental; -5% resistência elemental geral.", (Stat.ELEMENTAL_DAMAGE_PERCENT,F,.18), (Stat.GENERAL_ELEMENTAL_RESIST,F,-.05))
    passive("predador_ferido", "Predador Ferido", R, "+8% roubo de vida e +10% dano Físico; -10% cura recebida.", (Stat.LIFESTEAL_PERCENT,F,.08), (Stat.PHYSICAL_DAMAGE_PERCENT,F,.10), (Stat.HEALING_RECEIVED_PERCENT,F,-.10))
    reactive("remendo_noturno", "Remendo Noturno", R, "No fim do próprio turno, cura 1 PV.", TriggerEvent.ON_TURN_END, Effect(kind=EffectKind.HEAL, amount=1))
    reactive("colecionador_cascas", "Colecionador de Cascas", R, "Ao matar, ganha escudo de 4.", TriggerEvent.ON_KILL, Effect(kind=EffectKind.APPLY_SHIELD, amount=4))
    reactive("batida_escudo", "Batida do Escudo", R, "Ao bloquear, recupera 1 recurso.", TriggerEvent.ON_BLOCK, Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1))
    reactive("passo_oportunista", "Passo Oportunista", R, "Ao esquivar, fica Fortalecido por 1 turno.", TriggerEvent.ON_DODGE, _status("empowered",1))
    reactive("dente_vibora", "Dente de Víbora", R, "Críticos têm 25% de chance de envenenar por 2 turnos.", TriggerEvent.ON_CRIT, _status("poisoned"), "context", .25)
    reactive("moeda_dolorida", "Moeda Dolorida", R, "Ao sofrer dano, 25% de chance de recuperar 1 recurso.", TriggerEvent.ON_TAKE_DAMAGE, Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1), chance=.25)
    reactive("fita_sequencia", "Fita da Sequência", R, "Ao estender um combo por sequência, cura 2 PV.", TriggerEvent.ON_COMBO_EXTEND, Effect(kind=EffectKind.HEAL, amount=2))
    reactive("pacto_resgate", "Pacto de Resgate", R, "Quando um aliado cai, recupera 2 recurso.", TriggerEvent.ON_ALLY_DOWNED, Effect(kind=EffectKind.RESTORE_RESOURCE, amount=2))
    reactive("eco_resgate", "Eco do Resgate", R, "Ao ser revivido, fica Acelerado por 2 turnos.", TriggerEvent.ON_REVIVE, _status("acelerado"))
    reactive("oficio_batedor", "Ofício do Batedor", R, "Ao fechar combo em equipe, ganha escudo de 4.", TriggerEvent.ON_TEAM_COMBO, Effect(kind=EffectKind.APPLY_SHIELD, amount=4))
    reactive("martelo_ritual", "Martelo Ritual", R, "Ao quebrar Postura, enfraquece o alvo por 2 turnos.", TriggerEvent.ON_POISE_BREAK, _status("weakened"), "context")
    reactive("primeiro_sopro", "Primeiro Sopro", R, "No início do combate, ganha escudo de 6.", TriggerEvent.ON_COMBAT_START, Effect(kind=EffectKind.APPLY_SHIELD, amount=6))

    # Ten legendary passives; none bypasses active slots or grants unlimited revives.
    passive("rei_vidro", "Rei de Vidro", L, "+25% Ataque adicional; -20% PV máximos.", (Stat.ATTACK,M,.25), (Stat.MAX_HP,P,-.20))
    passive("montanha_andante", "Montanha Andante", L, "+35% Defesa adicional e +12 PV; -15% Ataque.", (Stat.DEFENSE,M,.35), (Stat.MAX_HP,F,12), (Stat.ATTACK,P,-.15))
    passive("constelacao_ferida", "Constelação Ferida", L, "+30% dano elemental; -10% resistência elemental geral.", (Stat.ELEMENTAL_DAMAGE_PERCENT,F,.30), (Stat.GENERAL_ELEMENTAL_RESIST,F,-.10))
    passive("relogio_sem_ponteiros", "Relógio sem Ponteiros", L, "+2 Velocidade e +0,8 recurso por turno.", (Stat.SPEED,F,2), (Stat.RESOURCE_REGEN_PER_TURN,F,.8))
    reactive("manto_amanhecer", "Manto do Amanhecer", L, "No início do combate, ganha escudo de 12.", TriggerEvent.ON_COMBAT_START, Effect(kind=EffectKind.APPLY_SHIELD, amount=12))
    reactive("banquete_cinzas", "Banquete de Cinzas", L, "Ao matar, recupera 2 recurso.", TriggerEvent.ON_KILL, Effect(kind=EffectKind.RESTORE_RESOURCE, amount=2))
    reactive("guarda_ultimo_fio", "Guarda do Último Fio", L, "Ao aparar com sucesso, ganha escudo de 4.", TriggerEvent.ON_PARRY_SUCCESS, Effect(kind=EffectKind.APPLY_SHIELD, amount=4))
    reactive("sutura_estrelas", "Sutura de Estrelas", L, "Críticos têm 35% de chance de curar 3 PV.", TriggerEvent.ON_CRIT, Effect(kind=EffectKind.HEAL, amount=3), chance=.35)
    reactive("sino_estilhacos", "Sino de Estilhaços", L, "Ao matar, causa 2 de dano Arcano a todos os inimigos vivos.", TriggerEvent.ON_KILL, Effect(kind=EffectKind.DAMAGE, amount=2, damage_element=DamageElement.ARCANE), "all_enemies")
    reactive("juramento_sobreviventes", "Juramento dos Sobreviventes", L, "Quando um aliado cai, ganha escudo de 10.", TriggerEvent.ON_ALLY_DOWNED, Effect(kind=EffectKind.APPLY_SHIELD, amount=10))

    descriptions = [
        "Dano de Gelo e Lentidão por 2 turnos.", "Dano de Raio em área; recarga de 2 turnos.",
        "Dano de Veneno e envenenamento por 3 turnos.", "Cura 6 PV de um aliado e remove 1 status nocivo.",
        "Escudo de 5 para todos os aliados; recarga de 3 turnos.", "Dano de Ar e Desequilibrado por 2 turnos.",
        "Revive um aliado com 25% de PV; uma vez por combate.", "Dano de Sombra e drena 2 recurso do alvo.",
        "Dano de Terra e 5 de dano de Postura.", "Dano de Água em área e Encharcado por 1 turno.",
        "Marca um inimigo e prepara um combo em equipe.", "Gasta 10% do PV atual para ficar Fortalecido por 3 turnos.",
    ]
    for index, (ability, description) in enumerate(zip(CARD_ABILITIES.values(), descriptions)):
        id = ability.id.removeprefix("card_")
        cards[id] = card_type(id=id, name=ability.name, rarity=L if index in (4,6,9) else R,
            description="Habilidade ativa: " + description, grants_ability=ability.id)
    return cards
