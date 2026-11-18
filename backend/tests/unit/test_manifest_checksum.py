"""Unit tests for cryptographic checksum verification of Release Manifests (TASK-005 Hardening)."""

from pathlib import Path

from scripts.release_manifest import ReleaseManifest


def test_deterministic_checksum_generation():
    manifest1 = ReleaseManifest.load(Path("docs/releases/v0.2.1.json"))
    manifest2 = ReleaseManifest.load(Path("docs/releases/v0.2.1.json"))

    checksum1 = manifest1.compute_checksum()
    checksum2 = manifest2.compute_checksum()

    assert len(checksum1) == 64
    assert checksum1 == checksum2
    assert manifest1.verify_checksum(checksum1) is True


def test_tampered_image_digest_detected():
    manifest = ReleaseManifest.load(Path("docs/releases/v0.2.1.json"))
    original_checksum = manifest.compute_checksum()

    # Tamper image digest
    tampered_digest = "sha256:" + "0" * 64
    manifest.images["backend"].digest = tampered_digest

    assert manifest.compute_checksum() != original_checksum
    assert manifest.verify_checksum(original_checksum) is False


def test_tampered_commit_sha_detected():
    manifest = ReleaseManifest.load(Path("docs/releases/v0.2.1.json"))
    original_checksum = manifest.compute_checksum()

    # Tamper commit sha
    manifest.commit_sha = "deadbeef1234"

    assert manifest.compute_checksum() != original_checksum
    assert manifest.verify_checksum(original_checksum) is False

