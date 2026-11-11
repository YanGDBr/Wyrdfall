from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.attributes import ATTRIBUTE_NAMES
from wyrdfall.domain.items import ACCESSORY_SLOTS, ENCHANTMENT_DEFS, ENCHANTMENT_SLOTS_BY_RARITY, EQUIPMENT_DEFS, equipped_item_ids, item_definition, item_enchantments, compatible_piece
from wyrdfall.domain.runes import ABILITY_RUNE_SLOTS_PER_ABILITY, BODY_RUNE_SLOTS, RUNE_DEFS, supports_ability_socket
from wyrdfall.domain.slots import ACTIVE_SLOT_LEVELS
from wyrdfall.domain.weapons import WEAPON_TYPE_DEFS
from wyrdfall.domain.inventory import equipment_comparison
from wyrdfall.domain.content import TALENT_TREES
from wyrdfall.engine.session import SessionError, _talent_tree_id_for
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, KeyValue, Panel, Rows, Tabbed, TitleBar

ARMOR_SLOTS = ("head", "body", "legs")
ARMOR_SLOT_LABELS = {"head": "Cabeça", "body": "Corpo", "legs": "Pernas"}

TABS = [
    ("habilidades", "Habilidades"),
    ("arma", "Arma"),
    ("runas", "Runas"),
    ("armadura", "Armadura"),
    ("encantamentos", "Encantamentos"),
    ("bolsa", "Bolsa e trocas"),
]


def stat_rows(hero, ruleset) -> list[tuple[str, str]]:
    """The computed stats a player actually reads when comparing gear."""
    s = hero.computed_stats(ruleset)
    rows = [
        ("PV", f"{hero.current_hp:.0f}/{s.max_hp:.0f}"),
        ("Ataque", f"{s.attack:.1f}"),
        ("Defesa", f"{s.defense:.1f}"),
        ("Velocidade", f"{s.speed:.1f}"),
        ("Crítico", f"{s.crit_chance:.0%} × {s.crit_mult:.2f}"),
        ("Esquiva", f"{s.dodge_chance:.0%}"),
        ("Bloqueio", f"{s.block_chance:.0%}"),
    ]
    if s.physical_damage_percent:
        rows.append(("Dano físico", f"+{s.physical_damage_percent:.0%}"))
    if s.elemental_damage_percent:
        rows.append(("Dano elemental", f"+{s.elemental_damage_percent:.0%}"))
    if s.weapon_damage_percent:
        rows.append(("Bônus da arma", f"+{s.weapon_damage_percent:.0%}"))
    if s.lifesteal_percent:
        rows.append(("Roubo de vida", f"{s.lifesteal_percent:.0%}"))
    if s.armor_penetration_percent:
        rows.append(("Penetração", f"{s.armor_penetration_percent:.0%}"))
    return rows


class EquipmentScreen(Screen):
    """Weapon-type selection, rune socketing (body and per-ability),
    Active Ability Slots, armor/accessories and enchantments -- one tab
    each, with the character's computed stats always visible on the
    left so every change shows its effect immediately."""

    CSS = """
    EquipmentScreen #side { width: 32; height: 100%; }
    EquipmentScreen #side Panel { height: auto; }
    EquipmentScreen #main { width: 1fr; height: 100%; }
    EquipmentScreen .pane { height: 100%; }
    EquipmentScreen .pane Panel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Equipamento")
            with Columns(classes="body fill"):
                with Vertical(id="side"):
                    with Panel("Atributos de combate", variant="accent"):
                        yield KeyValue(id="stats")
                    with Panel("Resumo"):
                        yield KeyValue(id="summary")
                with Vertical(id="main"):
                    tabbed = Tabbed(TABS, initial="habilidades", id="equipment-tabs")
                    tabbed.add_pane("habilidades", VerticalScroll(
                        Panel("Slots de Habilidade Ativa", Hint("", id="ability-slot-status"), Rows(id="ability-slot-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("arma", VerticalScroll(
                        Panel("Tipo de arma", Static("", id="weapon-status"), Hint("A arma escala com atributos e libera habilidades exclusivas enquanto equipada."), Rows(id="weapon-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("runas", VerticalScroll(
                        Panel("Runas corporais", Hint("", id="body-rune-status"), Rows(id="body-rune-rows")),
                        Panel("Absorver (Construto)", Rows(id="absorb-rune-rows"), id="absorb-panel"),
                        Panel("Runas de habilidade", Hint("Uma runa numa habilidade só afeta aquela habilidade."), Rows(id="ability-rune-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("armadura", VerticalScroll(
                        Panel("Armadura", Rows(id="armor-rows")),
                        Panel("Acessórios", Hint("", id="accessory-status"), Rows(id="accessory-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("encantamentos", VerticalScroll(
                        Panel("Encantamentos", Hint("Slots por raridade: Comum 1, Raro 2, Lendário 3."), Rows(id="enchantment-rows")),
                        classes="pane",
                    ))
                    tabbed.add_pane("bolsa", VerticalScroll(
                        Panel("Peças da equipe", Hint("Entregar remove a peça de você e a coloca na bolsa do aliado. Ele decide quando equipá-la."), Rows(id="trade-rows")),
                        classes="pane",
                    ))
                    yield tabbed
            with ButtonRow(classes="actions"):
                yield Button("Concluído", id="done", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._subscribed_client = self.app.client
        if self._subscribed_client is None:
            return
        self._subscribed_client.on_update(self.refresh_equipment)
        self.call_after_refresh(self.refresh_equipment)

    def on_unmount(self) -> None:
        if self._subscribed_client is not None:
            self._subscribed_client.off_update(self.refresh_equipment)

    def on_screen_resume(self) -> None:
        self.refresh_equipment()

    def _local_character_id(self) -> str:
        return next(iter(self._subscribed_client.local_character_ids()))

    def refresh_equipment(self) -> None:
        if not self.query("#stats"):
            return
        # Rebuilding the row lists removes and re-mounts buttons, which are
        # async operations in Textual -- coalesce through an exclusive
        # worker so a superseded render is cancelled instead of racing a
        # remove/mount against the next one (same pattern as AttributeScreen).
        self.run_worker(self._render_equipment, exclusive=True, group="equipment-rows")

    async def _render_equipment(self) -> None:
        client = self.app.client
        if client is None or client is not self._subscribed_client or getattr(self.app, "_leaving_run", False):
            return
        run = client.get_run()
        hero = next((c for c in run.party if c.id == self._local_character_id()), None)
        if hero is None:
            return

        self.query_one("#stats", KeyValue).set_rows(stat_rows(hero, client.ruleset))
        weapon_name = WEAPON_TYPE_DEFS[hero.equipped_weapon_type].name if hero.equipped_weapon_type else "Nenhuma"
        socketed = len(hero.body_rune_slots) + sum(len(v) for v in hero.ability_rune_slots.values())
        self.query_one("#summary", KeyValue).set_rows([
            ("Arma", weapon_name),
            ("Slots ativos", f"{len(hero.equipped_abilities)}/{hero.active_slot_capacity}"),
            ("Runas", f"{socketed} socketadas · {len(run.rune_inventory)} na bolsa"),
            ("Armadura", f"{len(hero.equipped_armor)}/3 peças"),
            ("Acessórios", f"{len(hero.equipped_accessories)}/{ACCESSORY_SLOTS}"),
        ])

        slots = hero.active_slot_capacity
        self.query_one("#ability-slot-status", Hint).update(
            f"{len(hero.equipped_abilities)}/{slots} usados -- +1 nos níveis {', '.join(str(lv) for lv in ACTIVE_SLOT_LEVELS)}. "
            "Só o que está equipado aparece em combate; Defender é sempre disponível."
        )
        await self._render_ability_slot_rows(client, hero, slots)
        self.query_one("#weapon-status", Static).update(f"Equipada: [bold]{escape(weapon_name)}[/bold]")
        await self._render_weapon_rows(hero)
        owned = ", ".join(RUNE_DEFS[r].name if r in RUNE_DEFS else r for r in run.rune_inventory) or "nenhuma"
        self.query_one("#body-rune-status", Hint).update(
            f"{len(hero.body_rune_slots)}/{BODY_RUNE_SLOTS} usadas -- na bolsa: {owned}"
        )
        await self._render_body_rune_rows(hero)
        await self._render_absorb_rune_rows(hero)
        await self._render_ability_rune_rows(client, hero)
        await self._render_armor_rows(hero)
        self.query_one("#accessory-status", Hint).update(
            f"{len(hero.equipped_accessories)}/{ACCESSORY_SLOTS} equipados"
        )
        await self._render_accessory_rows(hero)
        await self._render_enchantment_rows(hero)
        await self._render_trade_rows(hero)

    async def _render_ability_slot_rows(self, client, hero, slots: int) -> None:
        container = self.query_one("#ability-slot-rows", Rows)
        await container.remove_children()
        for ability_id in hero.abilities:
            ability = client.ruleset.abilities.get(ability_id)
            if ability is None:
                continue
            desc = f" [dim]-- {escape(ability.description)}[/dim]" if ability.description else ""
            if ability.universal:
                container.mount(Static(f"  [dim]∞[/dim] {escape(ability.name)}{desc}"))
            elif ability_id in hero.equipped_abilities:
                container.mount(Button(f"▣ {ability.name}{desc}", id=f"ability_unequip_{ability_id}", variant="primary"))
            else:
                full = len(hero.equipped_abilities) >= slots
                container.mount(Button(f"▢ {ability.name}{desc}", id=f"ability_equip_{ability_id}", disabled=full))

    async def _render_weapon_rows(self, hero) -> None:
        container = self.query_one("#weapon-rows", Rows)
        await container.remove_children()
        run = self._subscribed_client.get_run()
        for iid in run.inventory:
            item = item_definition(run, iid)
            if item is None or item.slot != "weapon":
                continue
            piece = run.equipment_instances[iid]
            if piece.owner_id not in (None, hero.id):
                continue
            weapon = WEAPON_TYPE_DEFS[item.weapon_type_id]
            is_current = iid == hero.equipped_weapon_id
            scaling = " + ".join(f"{ATTRIBUTE_NAMES[a][:3]} {w:.0%}" for a, w in weapon.scaling.items())
            label = f"{'▣' if is_current else '▢'} {item.name} · {iid[-6:]}  [dim]{scaling}[/dim]"
            container.mount(Button(label, id=f"weapon_{iid}", disabled=is_current or not compatible_piece(piece, hero),
                                   variant="primary" if is_current else "default"))
            if not is_current:
                container.mount(Static(escape(self._comparison(hero, iid))))

    def _comparison(self, hero, iid):
        tree = TALENT_TREES.get(_talent_tree_id_for(hero))
        return equipment_comparison(self._subscribed_client.get_run(), hero, iid, self._subscribed_client.ruleset, tree)

    async def _render_trade_rows(self, hero):
        container = self.query_one("#trade-rows", Rows)
        await container.remove_children()
        run = self._subscribed_client.get_run()
        names = {c.id: c.name for c in run.party}
        for iid in run.inventory:
            piece = run.equipment_instances[iid]
            item = item_definition(run, iid)
            owner = names.get(piece.owner_id, "Equipe")
            wearer = next((c.name for c in run.party if iid in equipped_item_ids(c)), "na bolsa")
            container.mount(Static(escape(f"{item.name} · {iid[-6:]} · {owner} · {wearer}")))
            if piece.owner_id == hero.id:
                for recipient in run.party:
                    if recipient.id != hero.id:
                        container.mount(Button(f"Entregar a {recipient.name}", id=f"transfer_{iid}__{recipient.id}",
                            disabled=not compatible_piece(piece, recipient)))

    def _owned_rune_ids(self) -> list[str]:
        """Distinct RuneDef ids in the run's rune inventory, in RUNE_DEFS order."""
        owned = set(self._subscribed_client.get_run().rune_inventory)
        return [rune_id for rune_id in RUNE_DEFS if rune_id in owned]

    async def _render_body_rune_rows(self, hero) -> None:
        container = self.query_one("#body-rune-rows", Rows)
        await container.remove_children()
        for rune_id in hero.body_rune_slots:
            rune = RUNE_DEFS.get(rune_id)
            name = rune.name if rune else rune_id
            desc = f" [dim]-- {escape(rune.description)}[/dim]" if rune else ""
            container.mount(Button(f"▣ {name}{desc}", id=f"body_remove_{rune_id}", variant="primary"))
        if len(hero.body_rune_slots) < BODY_RUNE_SLOTS:
            for rune_id in self._owned_rune_ids():
                if rune_id not in hero.body_rune_slots:
                    rune = RUNE_DEFS[rune_id]
                    container.mount(Button(f"▢ {rune.name} [dim]-- {escape(rune.description)}[/dim]", id=f"body_add_{rune_id}"))
        if not container.children:
            container.mount(Static("[dim]Nenhuma runa na bolsa -- elas caem de inimigos.[/dim]"))

    async def _render_absorb_rune_rows(self, hero) -> None:
        """Construto only (04-racas.md): absorb one rune's effect for the run."""
        container = self.query_one("#absorb-rune-rows", Rows)
        await container.remove_children()
        panel = self.query_one("#absorb-panel", Panel)
        panel.display = hero.race_id == "construto"
        if hero.race_id != "construto":
            return
        if hero.absorbed_rune_id is not None:
            name = RUNE_DEFS[hero.absorbed_rune_id].name if hero.absorbed_rune_id in RUNE_DEFS else hero.absorbed_rune_id
            container.mount(Static(f"Runa absorvida: [bold]{escape(name)}[/bold]"))
            return
        container.mount(Static("[dim]Absorva o efeito de uma runa da bolsa pelo resto da run, sem gastar slot (uma vez).[/dim]"))
        for rune_id in self._owned_rune_ids():
            container.mount(Button(f"Absorver {RUNE_DEFS[rune_id].name}", id=f"absorb_{rune_id}"))

    async def _render_ability_rune_rows(self, client, hero) -> None:
        container = self.query_one("#ability-rune-rows", Rows)
        await container.remove_children()
        owned = self._owned_rune_ids()
        for ability_id in hero.abilities:
            ability = client.ruleset.abilities.get(ability_id)
            ability_name = ability.name if ability else ability_id
            socketed = hero.ability_rune_slots.get(ability_id, [])
            container.mount(Static(f"[bold]{escape(ability_name)}[/bold] [dim]{len(socketed)}/{ABILITY_RUNE_SLOTS_PER_ABILITY}[/dim]"))
            for rune_id in socketed:
                name = RUNE_DEFS[rune_id].name if rune_id in RUNE_DEFS else rune_id
                container.mount(Button(f"  ▣ {name}", id=f"ability_remove_{ability_id}__{rune_id}", variant="primary"))
            if len(socketed) < ABILITY_RUNE_SLOTS_PER_ABILITY:
                for rune_id in owned:
                    if rune_id not in socketed and supports_ability_socket(RUNE_DEFS[rune_id]):
                        container.mount(Button(f"  ▢ {RUNE_DEFS[rune_id].name}", id=f"ability_add_{ability_id}__{rune_id}"))

    async def _render_armor_rows(self, hero) -> None:
        container = self.query_one("#armor-rows", Rows)
        await container.remove_children()
        run = self._subscribed_client.get_run()
        for slot in ARMOR_SLOTS:
            equipped_id = hero.equipped_armor.get(slot)
            item = item_definition(run, equipped_id) if equipped_id else None
            equipped_name = item.name if item else "[dim]vazio[/dim]"
            container.mount(Static(f"[bold]{ARMOR_SLOT_LABELS[slot]}[/bold]: {equipped_name}"))
            if equipped_id is not None:
                container.mount(Button(f"  ▣ {item.name if item else equipped_id}", id=f"armor_unequip_{slot}", variant="primary"))
            for item_id in dict.fromkeys(run.inventory):
                candidate = item_definition(run, item_id)
                if candidate is None or candidate.slot != slot or item_id == equipped_id or run.equipment_instances[item_id].owner_id not in (None, hero.id):
                    continue
                container.mount(Button(f"  ▢ {candidate.name} · {item_id[-6:]} [dim]({candidate.rarity.value})[/dim]", id=f"armor_equip_{slot}__{item_id}", disabled=not compatible_piece(run.equipment_instances[item_id], hero)))
                container.mount(Static(escape(self._comparison(hero, item_id))))

    async def _render_accessory_rows(self, hero) -> None:
        container = self.query_one("#accessory-rows", Rows)
        await container.remove_children()
        run = self._subscribed_client.get_run()
        for item_id in hero.equipped_accessories:
            name = item_definition(run, item_id).name
            container.mount(Button(f"▣ {name}", id=f"accessory_unequip_{item_id}", variant="primary"))
        if len(hero.equipped_accessories) < ACCESSORY_SLOTS:
            for item_id in dict.fromkeys(run.inventory):
                item = item_definition(self._subscribed_client.get_run(), item_id)
                if item is None or item.slot != "accessory" or item_id in hero.equipped_accessories or run.equipment_instances[item_id].owner_id not in (None, hero.id):
                    continue
                container.mount(Button(f"▢ {item.name} · {item_id[-6:]} [dim]({item.rarity.value})[/dim]", id=f"accessory_equip_{item_id}", disabled=not compatible_piece(run.equipment_instances[item_id], hero)))
                container.mount(Static(escape(self._comparison(hero, item_id))))
        if not container.children:
            container.mount(Static("[dim]Nenhum acessório encontrado ainda.[/dim]"))

    async def _render_enchantment_rows(self, hero) -> None:
        container = self.query_one("#enchantment-rows", Rows)
        await container.remove_children()
        for item_id in equipped_item_ids(hero):
            item = item_definition(self._subscribed_client.get_run(), item_id)
            if item is None:
                continue
            socketed = item_enchantments(hero, item_id)
            cap = ENCHANTMENT_SLOTS_BY_RARITY[self._subscribed_client.get_run().equipment_instances[item_id].rarity]
            container.mount(Static(f"[bold]{escape(item.name)}[/bold] [dim]{len(socketed)}/{cap}[/dim]"))
            for enchantment_id in socketed:
                name = ENCHANTMENT_DEFS[enchantment_id].name if enchantment_id in ENCHANTMENT_DEFS else enchantment_id
                container.mount(Static(f"  ✓ {escape(name)}"))
            if len(socketed) < cap:
                container.mount(Static("[dim]Gravar na Forja: 10 Fragmentos + 1 material da raridade da peça.[/dim]"))
        if not container.children:
            container.mount(Static("[dim]Equipe armadura ou acessórios para socketar encantamentos.[/dim]"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.app.client is None or self.app.client is not self._subscribed_client:
            return
        button_id = event.button.id or ""
        if button_id.startswith("tab_") or button_id == "":
            return
        character_id = self._local_character_id()
        if button_id.startswith("absorb_"):
            await self.app.client.absorb_rune(character_id, button_id.removeprefix("absorb_"))
            self.refresh_equipment()
            return
        client = self.app.client
        if button_id == "done":
            self.app.pop_screen()
        elif button_id.startswith("transfer_"):
            item_id, recipient_id = button_id.removeprefix("transfer_").split("__", 1)
            try:
                await client.transfer_equipment(character_id, recipient_id, item_id)
            except SessionError as exc:
                self.notify(str(exc), severity="warning")
        elif button_id.startswith("weapon_"):
            await client.equip_weapon(character_id, button_id.removeprefix("weapon_"))
        elif button_id.startswith("ability_equip_"):
            await client.equip_ability(character_id, button_id.removeprefix("ability_equip_"))
        elif button_id.startswith("ability_unequip_"):
            await client.unequip_ability(character_id, button_id.removeprefix("ability_unequip_"))
        elif button_id.startswith("body_add_"):
            await client.socket_rune(character_id, button_id.removeprefix("body_add_"), None)
        elif button_id.startswith("body_remove_"):
            await client.unsocket_rune(character_id, button_id.removeprefix("body_remove_"), None)
        elif button_id.startswith("ability_add_"):
            ability_id, rune_id = button_id.removeprefix("ability_add_").split("__", 1)
            await client.socket_rune(character_id, rune_id, ability_id)
        elif button_id.startswith("ability_remove_"):
            ability_id, rune_id = button_id.removeprefix("ability_remove_").split("__", 1)
            await client.unsocket_rune(character_id, rune_id, ability_id)
        elif button_id.startswith("armor_equip_"):
            slot, item_id = button_id.removeprefix("armor_equip_").split("__", 1)
            await client.equip_armor(character_id, slot, item_id)
        elif button_id.startswith("armor_unequip_"):
            await client.unequip_armor(character_id, button_id.removeprefix("armor_unequip_"))
        elif button_id.startswith("accessory_equip_"):
            await client.equip_accessory(character_id, button_id.removeprefix("accessory_equip_"))
        elif button_id.startswith("accessory_unequip_"):
            await client.unequip_accessory(character_id, button_id.removeprefix("accessory_unequip_"))
        elif button_id.startswith("enchant_socket_"):
            item_id, enchantment_id = button_id.removeprefix("enchant_socket_").split("__", 1)
            await client.socket_enchantment(character_id, item_id, enchantment_id)
