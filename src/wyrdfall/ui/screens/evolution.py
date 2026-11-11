from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Collapsible, Footer, Static

from wyrdfall.domain.models import EvolutionVariants
from wyrdfall.domain.specializations import (
    DAMAGE_ELEMENT_NAMES,
    SPECIALIZATION_DEFS,
    STAGE2_DEFS,
    alignment_category,
    archetype_affinity,
    elemental_affinity,
    evolution_name,
    evolution_offers,
    evolution_variant_choices,
    merge_evolution_variants,
    variant_descriptions,
)
from wyrdfall.engine.session import EVOLUTION_LEVEL, EVOLUTION_STAGE2_LEVEL, SessionError
from wyrdfall.ui.widgets import ButtonRow, Columns, Hint, KeyValue, Panel, TitleBar

_ARCHETYPE_NAMES = {"guerreiro": "Guerreiro", "patrulheiro": "Patrulheiro", "mistico": "Místico", "guardiao": "Guardião"}


class EvolutionScreen(Screen):
    """Pushed from DungeonScreen's 'Evoluir' button, only reachable once
    it's enabled (level >= EVOLUTION_LEVEL, not yet evolved, at least one
    Especialização qualifies -- or the Estágio 2 equivalent at
    EVOLUTION_STAGE2_LEVEL) -- but the actual pick is still re-validated
    server-side by GameSession.evolve_specialization, never trusted from
    this screen alone. Stage 1 and Stage 2 offers share the same button
    ids/flow; evolution_offers decides which list applies."""

    CSS = """
    EvolutionScreen #side { width: 32; height: 100%; }
    EvolutionScreen #side Panel { height: auto; }
    EvolutionScreen #offers { width: 1fr; height: 100%; }
    EvolutionScreen #offers Panel { height: auto; }
    EvolutionScreen #offers Button { margin-top: 1; }
    EvolutionScreen .variant-choice { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Evoluir Especialização", id="evolution-title")
            with Columns(classes="body fill"):
                with Vertical(id="side"):
                    with Panel("Sua Afinidade", variant="accent"):
                        yield Hint("Medida pelo que você usou nesta run. Ela decide o que é oferecido.")
                        yield KeyValue(id="affinity")
                    with Panel("Como funciona"):
                        yield Hint("A escolha é definitiva para o resto da run. Evoluir abre um ramo novo na sua árvore sem perder nada.")
                with VerticalScroll(id="offers"):
                    yield Static("", id="evolution-body")
            with ButtonRow(classes="actions"):
                yield Button("Cancelar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._client = self.app.client
        hero = self._local_character()
        self._stage = (hero.specialization_id, hero.stage2_specialization_id)
        self._choices: dict[str, tuple[str, EvolutionVariants]] = {}
        self._client.on_update(self._queue_refresh)
        self.call_after_refresh(self.refresh_options)

    def on_unmount(self) -> None:
        self._client.off_update(self._queue_refresh)

    def _queue_refresh(self) -> None:
        self.call_later(self.refresh_options)

    def _local_character_id(self) -> str:
        return next(iter(self._client.local_character_ids()))

    def _local_character(self):
        return next(c for c in self._client.get_run().party if c.id == self._local_character_id())

    def refresh_options(self) -> None:
        if self.app.screen is not self or self.app.client is not self._client:
            return
        character = self._local_character()
        if (character.specialization_id, character.stage2_specialization_id) != self._stage:
            self.app.pop_screen()
            return
        required = EVOLUTION_LEVEL if character.specialization_id is None else EVOLUTION_STAGE2_LEVEL
        options = evolution_offers(character) if character.level >= required else []
        if character.specialization_id is not None:
            base = SPECIALIZATION_DEFS.get(character.specialization_id)
            self.query_one("#evolution-title", TitleBar).update(
                f"Evoluir · Estágio 2{f' de {evolution_name(base.name, character.evolution_variants)}' if base else ''}"
            )
        affinity = archetype_affinity(character)
        rows = [(_ARCHETYPE_NAMES[a.value], _trend(share))
                for a, share in sorted(affinity.items(), key=lambda kv: -kv[1]) if share]
        elemental = elemental_affinity(character)
        rows.extend((DAMAGE_ELEMENT_NAMES[e], _trend(share))
                    for e, share in sorted(elemental.items(), key=lambda kv: -kv[1]) if share)
        rows.append(("Alinhamento", alignment_category(character.alignment_score).value.capitalize()))
        self.query_one("#affinity", KeyValue).set_rows(rows)

        body = self.query_one("#evolution-body", Static)
        if options:
            body.update("")
        elif character.level < required:
            body.update(f"Evolução disponível a partir do nível {required}.")
        elif character.specialization_id and not any(
            character.specialization_id in spec.from_specializations for spec in STAGE2_DEFS.values()
        ):
            body.update("Este caminho termina no primeiro estágio.")
        else:
            body.update("Nenhuma opção combina com sua afinidade, atributos, arma, raça e alinhamento atuais.")
        self.run_worker(
            self._render_options(options, evolution_variant_choices(character), character.evolution_variants),
            exclusive=True, group="evolution-options",
        )

    async def _render_options(self, options, additions, inherited) -> None:
        container = self.query_one("#offers", VerticalScroll)
        for existing in list(container.query(".spec-option")):
            await existing.remove()
        self._choices.clear()
        for spec in options:
            choices = []
            for index, choice in enumerate(additions):
                merged = merge_evolution_variants(inherited, choice)
                label = evolution_name(spec.name, merged)
                if index == 0:
                    button_id = f"spec_{spec.id}"
                else:
                    race = choice.race_id or "base"
                    alignment = choice.alignment.value if choice.alignment else "base"
                    element = choice.element.value if choice.element else "base"
                    button_id = f"variant_{spec.id}__{race}__{alignment}__{element}"
                self._choices[button_id] = (spec.id, choice)
                effects = " · ".join(variant_descriptions(merged)) or "Especialização base"
                choices.append(Vertical(
                    Static(f"{escape(label)} · {escape(effects)}"),
                    Button(f"Evoluir para {label}", id=button_id, variant="primary"),
                    classes="variant-choice",
                ))
            variant_picker = []
            if len(choices) > 1:
                names = [evolution_name(spec.name, merge_evolution_variants(inherited, v)) for v in additions[1:]]
                variant_picker = [
                    Static("Variantes disponíveis: " + escape(", ".join(names))),
                    Collapsible(*choices[1:], title="Escolher variantes e ver efeitos", id=f"variants_{spec.id}"),
                ]
            container.mount(Panel(
                spec.name,
                Static(escape(spec.description)), choices[0], *variant_picker,
                variant="accent", classes="spec-option",
            ))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
        elif button_id in self._choices and self.app.client is self._client:
            specialization_id, variants = self._choices[button_id]
            try:
                await self._client.evolve_specialization(self._local_character_id(), specialization_id, variants)
            except SessionError as exc:
                self.notify(str(exc), severity="warning")
                self.refresh_options()


def _trend(share: float) -> str:
    if share >= .6:
        return "Dominante"
    if share >= .25:
        return "Forte"
    return "Secundária"
