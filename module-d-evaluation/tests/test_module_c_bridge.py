"""Tests that Module D reaches Module C's real controller from any working directory."""

import module_c


def test_the_bridge_finds_module_c_next_to_this_module():
    assert (module_c.MODULE_C_DIR / "controller" / "scale_controller.py").is_file()


def test_the_bridge_exposes_module_cs_real_scale_to():
    controller = module_c.controller()

    assert controller.scale_to.__module__ == "controller.scale_controller"


def test_importing_the_controller_has_no_side_effects_on_the_audit_log():
    # Importing must not touch Docker or the audit log.
    log = module_c.MODULE_C_DIR / "logs" / "scale_actions.jsonl"
    before = log.read_bytes() if log.exists() else b""

    module_c.controller()

    after = log.read_bytes() if log.exists() else b""
    assert after == before
