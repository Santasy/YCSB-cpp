"""
The tabs this project shows — the workload's own UI composition.

A tab is a label plus a render function over the engine's
:class:`~benchgrid.plots.context.TabContext`; the renderers used here
(``render_panels``, ``render_curve``, ``render_pairs``) are generic, but *which*
tabs exist and what each one plots is project knowledge.  Each view opens with
the engine's own measure selector, so no tab writes a step of its own.

Streamlit arrives with this module, which is why the headless CLI imports the
data layer without it.
"""

from __future__ import annotations

from functools import partial

from benchgrid.plots.app import render_curve, render_pairs, render_panels

from .bridge import Tab
from .curves import GROWTH_BEST, GROWTH_PER_TARGET, TRADEOFF

TABS = [
    Tab("Metrics", render_panels),
    Tab("Growth — best target size", partial(render_curve, spec=GROWTH_BEST)),
    Tab("Growth — per target size", partial(render_curve, spec=GROWTH_PER_TARGET)),
    Tab("Trade-off — time vs memory", partial(render_pairs, spec=TRADEOFF)),
]

__all__ = ["TABS"]
