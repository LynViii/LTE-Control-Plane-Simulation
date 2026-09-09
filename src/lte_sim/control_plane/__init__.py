"""LTE control-plane implementation package.

Import concrete engine symbols from ``lte_sim.control_plane.engine``.  This
package initializer stays lightweight so shared metadata can be imported by
fault-injection code without creating circular imports.
"""
from .specs import STEP_LABELS, TIMER_SPECS, timer_spec_for_stage

__all__ = ["STEP_LABELS", "TIMER_SPECS", "timer_spec_for_stage"]
