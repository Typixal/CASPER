"""Module D drives the SAME scale controller as CASPER's predictive policy.

That shared knob is the whole experimental control: two brains, one knob.
These tests check D reaches Module C's real controller -- by file location,
not by the caller's working directory, which is how the old README example
(`sys.path.insert(0, "../casper-module-c")`) would break.
"""

import module_c


def test_the_bridge_finds_module_c_next_to_this_module():
    assert (module_c.MODULE_C_DIR / "controller" / "scale_controller.py").is_file()


def test_the_bridge_exposes_module_cs_real_scale_to():
    controller = module_c.controller()

    assert controller.scale_to.__module__ == "controller.scale_controller"


def test_importing_the_controller_has_no_side_effects_on_the_audit_log():
    # Module C promises import-safety. If importing it touched Docker or the
    # log, every Module D test run would pollute the real audit trail.
    log = module_c.MODULE_C_DIR / "logs" / "scale_actions.jsonl"
    before = log.read_bytes() if log.exists() else b""

    module_c.controller()

    after = log.read_bytes() if log.exists() else b""
    assert after == before
