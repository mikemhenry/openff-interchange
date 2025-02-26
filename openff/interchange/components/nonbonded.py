"""Models for non-standard non-bonded treatments."""
from typing_extensions import Literal

from openff.interchange.components.potentials import PotentialHandler


class BuckinghamvdWHandler(PotentialHandler):
    """Handler storing Buckingham-style vdW potentials."""

    type: Literal["Buckingham-6"] = "Buckingham-6"
    expression: Literal["a*exp(-b*r)-c*r**-6"] = "a*exp(-b*r)-c*r**-6"
    mixing_rule: Literal["buckingham"] = "buckingham"
    method: str = "cutoff"
    cutoff: float = 9.0
    scale_13: float = 0.0
    scale_14: float = 0.5
    scale_15: float = 1.0
