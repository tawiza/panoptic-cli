"""Synchronisation avec le CDN panoptic — `panoptic update`.

Pattern :
  1. fetch `panoptic.tawiza.fr/data/manifest.json`
  2. comparer version locale vs distante
  3. si distant plus frais, télécharger `panoptic.sqlite` + vérifier SHA-256
  4. écrire dans `~/.cache/panoptic/panoptic.sqlite` (priorité sur DB bundled)

La CLI lit la DB en cascade :
  1. `$PANOPTIC_DB` (override dev/test)
  2. `~/.cache/panoptic/panoptic.sqlite` (si plus récent)
  3. DB bundled dans le package (installée par pip)

Pas de daemon, pas d'auto-update : c'est le militant qui décide quand
rafraîchir. Souveraineté locale.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_URL = "https://panoptic.tawiza.fr/data/manifest.json"
CACHE_DIR = Path.home() / ".cache" / "panoptic"
CACHED_DB_PATH = CACHE_DIR / "panoptic.sqlite"


@dataclass
class Manifest:
    version: str
    generated_at: str
    sqlite_url: str
    sqlite_sha256: str
    sqlite_size_bytes: int
    counts: dict[str, int]
    sources: dict[str, dict]


def parse_manifest(raw: dict) -> Manifest:
    return Manifest(
        version=raw.get("version", "?"),
        generated_at=raw.get("generated_at", ""),
        sqlite_url=raw["sqlite"]["url"],
        sqlite_sha256=raw["sqlite"]["sha256"],
        sqlite_size_bytes=int(raw["sqlite"]["size_bytes"]),
        counts=raw.get("counts", {}),
        sources=raw.get("sources", {}),
    )


def fetch_manifest(url: str = MANIFEST_URL, timeout: int = 10) -> Manifest:
    """Télécharge et parse le manifest distant. Lève sur erreur réseau."""
    req = urllib.request.Request(url, headers={"User-Agent": "panoptic-tawiza/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return parse_manifest(data)


def local_version(db_path: Path) -> str | None:
    """Lit la version embarquée dans la table meta de la DB locale."""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'version'"
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except sqlite3.DatabaseError:
        return None


def download_db(manifest: Manifest, target: Path, timeout: int = 60) -> None:
    """Télécharge puis vérifie le SHA-256 avant d'écrire à destination finale."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".partial")
    req = urllib.request.Request(
        manifest.sqlite_url, headers={"User-Agent": "panoptic-tawiza/0.1"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)

    sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if sha != manifest.sqlite_sha256:
        tmp.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch: remote={manifest.sqlite_sha256[:12]}…, "
            f"downloaded={sha[:12]}… — fichier ignoré, DB locale inchangée."
        )

    tmp.replace(target)


def needs_update(local: str | None, remote: str) -> bool:
    """Compare les versions (format YYYY-MM-DD)."""
    if not local:
        return True
    try:
        l_dt = datetime.strptime(local, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        r_dt = datetime.strptime(remote, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return r_dt > l_dt
    except ValueError:
        # si format inattendu, on force à jour
        return local != remote


def effective_db_path() -> Path:
    """Résout la DB à utiliser (ordre : env → cache user → bundle)."""
    import os
    override = os.environ.get("PANOPTIC_DB")
    if override:
        return Path(override)
    bundled = Path(__file__).parent / "data" / "panoptic.sqlite"
    if CACHED_DB_PATH.exists():
        # Si on a une version cache, vérifier qu'elle est ≥ bundled
        cache_v = local_version(CACHED_DB_PATH)
        bundle_v = local_version(bundled) if bundled.exists() else None
        if not bundle_v or not cache_v or cache_v >= bundle_v:
            return CACHED_DB_PATH
    return bundled
