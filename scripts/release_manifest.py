"""Release manifest specification and utility functions.

Implements TASK-005 requirements:
- Stores Git tag/release, commit SHA, image digests, and migration revision.
- Strictly validates that digests use sha256 and forbids the 'latest' tag.
- Enables end-to-end traceability between `/api/version`, deployment, and registry artifacts (E08).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.fault_config import FaultConfig

HEX_SHA_REGEX = re.compile(r"^[0-9a-fA-F]{7,40}$")
DIGEST_REGEX = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


@dataclass
class ImageSpec:
    repository: str
    tag: str
    digest: str

    def validate(self, service_name: str) -> list[str]:
        errors: list[str] = []
        if not self.repository:
            errors.append(f"Image '{service_name}' repository cannot be empty.")
        if not self.tag:
            errors.append(f"Image '{service_name}' tag cannot be empty.")
        if self.tag.lower() == "latest":
            errors.append(
                f"Image '{service_name}' uses forbidden tag 'latest'. Pinned tag required."
            )
        if not self.digest:
            errors.append(f"Image '{service_name}' digest is required.")
        elif not DIGEST_REGEX.match(self.digest):
            errors.append(
                f"Image '{service_name}' digest '{self.digest}' is invalid. "
                "Must be in format 'sha256:<64-hex-characters>'."
            )
        return errors

    @property
    def pinned_reference(self) -> str:
        """Returns repository@digest for deterministic deployment without tag mutations."""
        return f"{self.repository}@{self.digest}"


@dataclass
class ReleaseManifest:
    release: str
    commit_sha: str
    migration_revision: str
    images: dict[str, ImageSpec]
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    schema_version: str = "1.0.0"
    compatibility: dict[str, Any] = field(
        default_factory=lambda: {
            "min_compatible_schema": "20261007_0001",
            "rollback_window_supported": True,
        }
    )
    fault: FaultConfig = field(default_factory=FaultConfig)

    @property
    def backend_image(self) -> ImageSpec | None:
        """Returns ImageSpec for the backend service if declared."""
        return self.images.get("backend")

    @property
    def frontend_image(self) -> ImageSpec | None:
        """Returns ImageSpec for the frontend service if declared."""
        return self.images.get("frontend")

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.release or not self.release.strip():
            errors.append("Release identifier cannot be empty.")
        elif self.release.strip().lower() == "latest":
            errors.append("Release cannot be named 'latest'.")

        if not self.commit_sha or not HEX_SHA_REGEX.match(self.commit_sha.strip()):
            errors.append(
                f"Commit SHA '{self.commit_sha}' is invalid. Must be 7-40 hex characters."
            )

        if not self.migration_revision or not self.migration_revision.strip():
            errors.append("Migration revision cannot be empty.")

        if not self.images:
            errors.append("Manifest must declare at least one service image.")
        else:
            for service_name, spec in self.images.items():
                errors.extend(spec.validate(service_name))

        errors.extend(self.fault.validate())
        return errors

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Ensure images have properly serialized dict representations
        data["images"] = {name: asdict(spec) for name, spec in self.images.items()}
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def save(self, path: Path | str) -> None:
        errors = self.validate()
        if errors:
            raise ValueError(f"Cannot save invalid manifest: {'; '.join(errors)}")
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleaseManifest:
        images_raw = data.get("images", {})
        images: dict[str, ImageSpec] = {}
        for name, spec_data in images_raw.items():
            if isinstance(spec_data, ImageSpec):
                images[name] = spec_data
            elif isinstance(spec_data, dict):
                images[name] = ImageSpec(
                    repository=str(spec_data.get("repository", "")),
                    tag=str(spec_data.get("tag", "")),
                    digest=str(spec_data.get("digest", "")),
                )
            else:
                raise TypeError(f"Invalid image spec format for '{name}'.")

        manifest = cls(
            release=str(data.get("release", "")),
            commit_sha=str(data.get("commit_sha", "")),
            migration_revision=str(data.get("migration_revision", "")),
            images=images,
            created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
            schema_version=str(data.get("schema_version", "1.0.0")),
            compatibility=dict(data.get("compatibility", {})),
            fault=FaultConfig(**data.get("fault", {})),
        )
        return manifest

    @classmethod
    def load(cls, path: Path | str) -> ReleaseManifest:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Manifest file not found: {file_path}")
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
        manifest = cls.from_dict(data)
        errors = manifest.validate()
        if errors:
            raise ValueError(f"Loaded manifest from {file_path} is invalid: {'; '.join(errors)}")
        return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release manifest management tool for Booking API")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a new release manifest")
    create_parser.add_argument(
        "--release", required=True, help="Release version / Git tag (e.g. v0.1.0)"
    )
    create_parser.add_argument(
        "--commit-sha", required=True, help="Git commit SHA (40-char or short)"
    )
    create_parser.add_argument(
        "--migration-revision",
        required=True,
        help="Target database migration revision (e.g. 20261007_0001)",
    )
    create_parser.add_argument(
        "--backend-repo",
        default="ghcr.io/cuongmotnang/booking-backend",
        help="Backend image repository",
    )
    create_parser.add_argument(
        "--backend-digest",
        required=True,
        help="Backend image digest (must start with sha256:)",
    )
    create_parser.add_argument(
        "--frontend-repo",
        default="ghcr.io/cuongmotnang/booking-frontend",
        help="Frontend image repository",
    )
    create_parser.add_argument(
        "--frontend-digest",
        default=None,
        help="Frontend image digest (optional, must start with sha256: if provided)",
    )
    create_parser.add_argument(
        "--fault-config",
        help="Optional JSON fault config (mode, rate, until or duration_seconds, latency_seconds)",
    )
    create_parser.add_argument(
        "--output",
        required=True,
        help="Path where the JSON manifest will be saved",
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate an existing release manifest"
    )
    validate_parser.add_argument("--manifest", required=True, help="Path to manifest JSON file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create":
        images: dict[str, ImageSpec] = {
            "backend": ImageSpec(
                repository=args.backend_repo,
                tag=args.release,
                digest=args.backend_digest,
            )
        }
        if args.frontend_digest:
            images["frontend"] = ImageSpec(
                repository=args.frontend_repo,
                tag=args.release,
                digest=args.frontend_digest,
            )
        manifest = ReleaseManifest(
            release=args.release,
            commit_sha=args.commit_sha,
            migration_revision=args.migration_revision,
            images=images,
            fault=FaultConfig(**json.loads(Path(args.fault_config).read_text(encoding="utf-8")))
            if args.fault_config
            else FaultConfig(),
        )
        manifest.save(args.output)
        print(f"Manifest successfully created and saved to: {args.output}")

    elif args.command == "validate":
        manifest = ReleaseManifest.load(args.manifest)
        print(f"Manifest {args.manifest} is valid!")
        print(f"Release: {manifest.release} (Commit: {manifest.commit_sha})")
        print(f"Migration: {manifest.migration_revision}")
        for svc, img in manifest.images.items():
            print(f"  - {svc}: {img.pinned_reference}")


if __name__ == "__main__":
    main()
