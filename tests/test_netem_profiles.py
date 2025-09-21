from __future__ import annotations

import json
from pathlib import Path
from typing import List, Sequence

import pytest

from scripts import netem_profiles


def test_load_profiles_returns_expected_shape() -> None:
    profiles = netem_profiles.load_profiles()
    assert sorted(profiles) == [
        "mobile-edge-constrained",
        "regional-loss-burst",
        "steady-latency",
    ]
    steady = profiles["steady-latency"]
    assert steady.delay_ms == pytest.approx(80.0)
    assert steady.jitter_ms == pytest.approx(20.0)
    assert steady.loss_percent == pytest.approx(0.2)
    assert steady.rate_mbit == pytest.approx(200.0)
    assert steady.tags == ("steady", "baseline", "observability")


def test_build_apply_commands_contains_expected_flags() -> None:
    profile = netem_profiles.load_profiles()["regional-loss-burst"]
    commands = profile.build_apply_commands("eth0")
    first_command = commands[0]
    assert first_command[:5] == ["tc", "qdisc", "replace", "dev", "eth0"]
    assert "delay" in first_command
    assert "reorder" in first_command
    assert "duplicate" in first_command
    assert commands[1] == ["tc", "qdisc", "show", "dev", "eth0"]


def test_apply_and_clear_profile_logs_commands(tmp_path: Path) -> None:
    profile = netem_profiles.load_profiles()["mobile-edge-constrained"]
    log_dir = tmp_path / "logs"
    logger = netem_profiles.create_logger(log_dir, "eth1")
    executed: List[Sequence[str]] = []

    def runner(command: Sequence[str]) -> None:
        executed.append(tuple(command))

    netem_profiles.apply_profile(profile, "eth1", runner=runner, logger=logger)
    netem_profiles.clear_profile("eth1", runner=runner, logger=logger)

    assert executed[0][:4] == ("tc", "qdisc", "replace", "dev")
    assert executed[-1][:4] == ("tc", "qdisc", "del", "dev")

    log_path = log_dir / "eth1.log"
    log_content = log_path.read_text(encoding="utf-8")
    assert "Applying profile 'mobile-edge-constrained'" in log_content
    assert "Clearing netem state on interface 'eth1'" in log_content


def test_list_profiles_serialises_to_json() -> None:
    profiles = netem_profiles.load_profiles()
    summary = json.loads(netem_profiles.list_profiles(profiles))
    assert set(summary) == set(profiles)
    for entry in summary.values():
        assert "description" in entry
        assert "tc" in entry
        assert entry["tc"]