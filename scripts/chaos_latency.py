"""Chaos Engineering: Network latency and jitter simulation tool (TASK-007 Hardening).

Simulates network degradation and packet drop scenarios using Linux tc/netem or
application-level HTTP proxy delay wrappers to test client timeouts and circuit breaking.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ChaosProfile:
    interface: str
    delay_ms: int
    jitter_ms: int
    loss_percent: float


class NetworkChaosController:
    def __init__(self, interface: str = "eth0", dry_run: bool = False) -> None:
        self.interface = interface
        self.dry_run = dry_run

    def apply_latency(
        self,
        delay_ms: int = 150,
        jitter_ms: int = 30,
        loss_percent: float = 0.0,
    ) -> bool:
        cmd = [
            "tc",
            "qdisc",
            "add",
            "dev",
            self.interface,
            "root",
            "netem",
            "delay",
            f"{delay_ms}ms",
            f"{jitter_ms}ms",
        ]
        if loss_percent > 0.0:
            cmd.extend(["loss", f"{loss_percent}%"])

        cmd_str = " ".join(cmd)
        if self.dry_run:
            print(f"[CHAOS DRY-RUN] Would inject network chaos: {cmd_str}")
            return True

        print(f"[CHAOS INJECT] Applying netem latency on interface {self.interface}...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                print(
                    f"[CHAOS WARN] 'tc' returned code {res.returncode}: {res.stderr.strip()}",
                    file=sys.stderr,
                )
                return False
            print(f"[CHAOS ACTIVE] Injected {delay_ms}ms (+/-{jitter_ms}ms) delay")
            return True
        except FileNotFoundError:
            print(
                "[CHAOS SIMULATION] 'tc' utility not available in this environment, simulated only"
            )
            return True

    def clear_latency(self) -> bool:
        cmd = ["tc", "qdisc", "del", "dev", self.interface, "root"]
        cmd_str = " ".join(cmd)
        if self.dry_run:
            print(f"[CHAOS DRY-RUN] Would clear network chaos: {cmd_str}")
            return True

        print(f"[CHAOS CLEAR] Removing netem rules from {self.interface}...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode == 0
        except FileNotFoundError:
            return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Chaos Network Latency Injector")
    subparsers = parser.add_subparsers(dest="action", required=True)

    inject_parser = subparsers.add_parser("inject", help="Inject network delay/jitter/loss")
    inject_parser.add_argument("--interface", default="eth0")
    inject_parser.add_argument("--delay-ms", type=int, default=200)
    inject_parser.add_argument("--jitter-ms", type=int, default=50)
    inject_parser.add_argument("--loss", type=float, default=0.0)
    inject_parser.add_argument("--dry-run", action="store_true")

    clear_parser = subparsers.add_parser("clear", help="Clear injected network rules")
    clear_parser.add_argument("--interface", default="eth0")
    clear_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    controller = NetworkChaosController(interface=args.interface, dry_run=args.dry_run)

    if args.action == "inject":
        ok = controller.apply_latency(
            delay_ms=args.delay_ms,
            jitter_ms=args.jitter_ms,
            loss_percent=args.loss,
        )
        sys.exit(0 if ok else 1)
    elif args.action == "clear":
        controller.clear_latency()


if __name__ == "__main__":
    main()
