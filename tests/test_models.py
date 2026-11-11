from wyrdfall.domain.models import Modifier, ModifierKind, Stat, StatBlock, compute_stats


def test_flat_then_percent_then_more_stack_correctly():
    base = StatBlock(attack=10.0)
    modifiers = [
        Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=5.0, source="a"),
        Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.20, source="b"),
        Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.10, source="c"),
        Modifier(stat=Stat.ATTACK, kind=ModifierKind.MORE, value=0.50, source="d"),
    ]
    result = compute_stats(base, modifiers)
    # (10 + 5) * (1 + 0.20 + 0.10) * (1 + 0.50) = 15 * 1.30 * 1.50 = 29.25
    assert result.attack == 29.25


def test_unrelated_stats_are_untouched():
    base = StatBlock(attack=10.0, defense=3.0)
    modifiers = [Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=5.0, source="a")]
    result = compute_stats(base, modifiers)
    assert result.defense == 3.0
