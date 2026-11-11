from wyrdfall.domain.character import Ruleset
from wyrdfall.domain.content.abilities import ABILITY_DEFS
from wyrdfall.domain.content.statuses import STATUS_DEFS
from wyrdfall.domain.content.summons import SUMMON_DEFS
from wyrdfall.domain.content.transforms import TRANSFORM_DEFS


def build_ruleset() -> Ruleset:
    return Ruleset(
        abilities=dict(ABILITY_DEFS), statuses=dict(STATUS_DEFS), summons=dict(SUMMON_DEFS),
        transforms=dict(TRANSFORM_DEFS),
    )
