"""Verified, recoverable ZIP archives for rotated logs and startup backgrounds."""

import hashlib
import json
import os
import re
import stat
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath


_NUMBERED_LOG = re.compile(r"zx-slm-tool(?:-WARNING|-ERROR)?-0*[1-9][0-9]*\.log\Z")
_ACTIVE_LOGS = frozenset(("zx-slm-tool.log", "zx-slm-tool-WARNING.log", "zx-slm-tool-ERROR.log"))
_BATCH_ID = re.compile(r"[a-f0-9]{32}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_CHUNK_SIZE = 1024 * 1024


class _SourceChanged(ValueError):
    pass


def _absolute(path):
    return Path(os.path.abspath(os.fspath(path)))


def _reject_links(path):
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ValueError("Symbolic links and junctions are not archive sources")


def _is_regular(path):
    _reject_links(path)
    return stat.S_ISREG(os.lstat(path).st_mode)


def _sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def move_no_replace(source, target):
    """Move a regular file without ever replacing an existing destination."""
    source, target = _absolute(source), _absolute(target)
    if not _is_regular(source):
        raise ValueError("Only regular files can be moved")
    _reject_links(target.parent)
    if os.name == "nt":
        os.rename(source, target)
        return
    os.link(source, target, follow_symlinks=False)
    try:
        os.unlink(source)
    except OSError:
        # The source still exists. Remove only the hard link we just created.
        try:
            if os.path.samestat(os.lstat(source), os.lstat(target)):
                os.unlink(target)
        except OSError:
            pass
        raise


class ArchiveManager:
    def __init__(self, log_dir, archive_dir, max_size_mb=5120, diagnostic=print, *, background_dir=None):
        self.log_dir = _absolute(log_dir)
        self.archive_dir = _absolute(archive_dir)
        self.background_dir = _absolute(background_dir) if background_dir is not None else None
        self.max_size_mb = max_size_mb
        self.diagnostic = diagnostic
        # Remains true when the detached staging tree needs a later cleanup.
        self.background_reset_completed = False
        patcher = sys.modules.get("eventlet.patcher")
        native_threading = patcher.original("threading") if patcher is not None else threading
        self.lock = native_threading.RLock()

    def _report(self, error):
        try:
            self.diagnostic("[Log archive] " + str(error))
        except Exception:
            pass

    def _ensure_archive_dir(self):
        _reject_links(self.archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        if not self.archive_dir.is_dir():
            raise ValueError("Archive destination must be a directory")

    def _relative_path(self, value):
        if not isinstance(value, str) or not value or "\\" in value or ":" in value:
            raise ValueError("Invalid path in archive manifest")
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
            raise ValueError("Archive manifest path escapes its source directory")
        return path

    def _source_path(self, batch, entry, *, staged=False):
        relative = self._relative_path(entry["path"])
        root = self.log_dir
        if batch["kind"] == "background":
            root = self._background_root(batch)
            if staged:
                root = self._staging_path(batch)
        path = root.joinpath(*relative.parts)
        _reject_links(path)
        return path

    def _background_root(self, batch):
        if self.background_dir is None or batch.get("source_root") != str(self.background_dir):
            raise ValueError("Background recovery requires its configured source directory")
        root = self.background_dir
        if root == root.parent or self.archive_dir == root or root in self.archive_dir.parents:
            raise ValueError("Archive destination cannot be inside the background source")
        if root == self.log_dir or root in self.log_dir.parents:
            raise ValueError("Background source cannot contain the log directory")
        _reject_links(root)
        return root

    def _staging_path(self, batch):
        root = self._background_root(batch)
        stage = root.parent / ("." + root.name + ".archive-" + batch["id"])
        _reject_links(stage)
        return stage

    def _manifest_path(self, batch):
        return self.archive_dir / (".batch-" + batch["id"] + ".json")

    def _write_manifest(self, batch):
        target = self._manifest_path(batch)
        _reject_links(target)
        temporary = self.archive_dir / (target.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as output:
                json.dump(batch, output, ensure_ascii=True, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
            _sync_directory(self.archive_dir)
        finally:
            if temporary.exists():
                os.unlink(temporary)

    def _validate_batch(self, batch, manifest_path):
        if not isinstance(batch, dict) or batch.get("version") != 1:
            raise ValueError("Unsupported archive manifest")
        batch_id = batch.get("id")
        if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id):
            raise ValueError("Invalid archive batch identifier")
        if manifest_path != self._manifest_path(batch):
            raise ValueError("Archive manifest name does not match its batch")
        kind = batch.get("kind")
        if kind not in ("runtime", "startup", "background"):
            raise ValueError("Unknown archive batch kind")
        if batch.get("state") not in ("prepared", "published", "staging", "reset"):
            raise ValueError("Unknown archive transaction state")
        if kind != "background" and batch["state"] in ("staging", "reset"):
            raise ValueError("Unexpected log archive transaction state")
        name = batch.get("zip_name")
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name)
                or not name.startswith(kind + "-") or not name.endswith("-" + batch_id + ".zip")):
            raise ValueError("Invalid archive ZIP name")
        if batch.get("temp_name") != "." + name + ".tmp":
            raise ValueError("Invalid temporary ZIP name")
        entries = batch.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Missing archive manifest entries")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid archive entry")
            relative = self._relative_path(entry.get("path"))
            if entry["path"] in seen:
                raise ValueError("Duplicate source path in archive manifest")
            seen.add(entry["path"])
            if kind != "background":
                allowed = bool(_NUMBERED_LOG.fullmatch(entry["path"]))
                if kind == "startup":
                    allowed = allowed or entry["path"] in _ACTIVE_LOGS
                if len(relative.parts) != 1 or not allowed:
                    raise ValueError("Log archive source is not an allowed log file")
            for field in ("size", "mtime_ns"):
                if type(entry.get(field)) is not int or entry[field] < 0:
                    raise ValueError("Invalid archive source fingerprint")
            if not isinstance(entry.get("sha256"), str) or not _SHA256.fullmatch(entry["sha256"]):
                raise ValueError("Invalid archive source digest")
            if "removed" in entry and type(entry["removed"]) is not bool:
                raise ValueError("Invalid archive deletion state")
            self._source_path(batch, entry)
        if kind == "background":
            self._background_root(batch)
            directories = batch.get("directories")
            if not isinstance(directories, list) or len(set(directories)) != len(directories):
                raise ValueError("Invalid archive directory list")
            for directory in directories:
                self._relative_path(directory)
            if set(directories) & seen:
                raise ValueError("Archive path has conflicting types")
            self._staging_path(batch)

    def _read_manifest(self, path):
        if not _is_regular(path):
            raise ValueError("Archive manifest must be a regular file")
        with path.open("r", encoding="utf-8") as source:
            batch = json.load(source)
        self._validate_batch(batch, path)
        return batch

    def _fingerprint(self, path):
        _reject_links(path)
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Archive source must be a regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if not os.path.samestat(before, opened):
                raise _SourceChanged("Archive source changed while opening")
            for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
            after = os.fstat(source.fileno())
        current = os.lstat(path)
        if (not os.path.samestat(before, after) or not os.path.samestat(after, current)
                or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                or (after.st_size, after.st_mtime_ns) != (current.st_size, current.st_mtime_ns)):
            raise _SourceChanged("Archive source changed while reading")
        return {"size": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": digest.hexdigest()}

    def _matches(self, path, entry):
        actual = self._fingerprint(path)
        return all(actual[field] == entry[field] for field in ("size", "mtime_ns", "sha256"))

    def _scan_background(self, root):
        _reject_links(root)
        if not root.is_dir():
            raise ValueError("Background source must be a directory")
        entries, directories = [], []

        def scan_failed(error):
            raise error

        for current, subdirectories, filenames in os.walk(root, followlinks=False, onerror=scan_failed):
            for name in sorted(subdirectories):
                path = Path(current) / name
                _reject_links(path)
                if not stat.S_ISDIR(os.lstat(path).st_mode):
                    raise ValueError("Background source contains a non-directory")
                directories.append(path.relative_to(root).as_posix())
            for name in sorted(filenames):
                path = Path(current) / name
                entries.append({"path": path.relative_to(root).as_posix(), **self._fingerprint(path)})
        entries.sort(key=lambda entry: entry["path"])
        return entries, sorted(directories)

    def _archive_name(self, batch, relative):
        if batch["kind"] == "background":
            return self._background_root(batch).name + "/" + relative
        return relative

    def _validate_sources(self, batch, *, staged=False, exact_tree=False):
        if exact_tree:
            root = self._staging_path(batch) if staged else self._background_root(batch)
            entries, directories = self._scan_background(root)
            expected = [{key: entry[key] for key in ("path", "size", "mtime_ns", "sha256")}
                        for entry in batch["entries"] if not entry.get("removed")]
            if entries != expected or directories != batch["directories"]:
                raise _SourceChanged("Background source tree changed after archive preparation")
            return
        for entry in batch["entries"]:
            if entry.get("removed"):
                continue
            source = self._source_path(batch, entry, staged=staged)
            try:
                matches = self._matches(source, entry)
            except FileNotFoundError:
                if batch["state"] != "prepared":
                    continue
                raise
            if not matches:
                raise _SourceChanged("Archive source fingerprint changed: " + entry["path"])

    def _verify_zip(self, path, batch):
        if not _is_regular(path):
            raise ValueError("Archive ZIP must be a regular file")
        with zipfile.ZipFile(path, "r") as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive ZIP failed CRC validation")
            expected_names = {self._archive_name(batch, entry["path"]) for entry in batch["entries"]}
            if batch["kind"] == "background":
                expected_names.add(self._background_root(batch).name + "/")
                expected_names.update(self._archive_name(batch, directory) + "/"
                                      for directory in batch["directories"])
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != expected_names:
                raise ValueError("Archive ZIP entries do not match the durable manifest")
            for entry in batch["entries"]:
                name = self._archive_name(batch, entry["path"])
                if archive.getinfo(name).file_size != entry["size"]:
                    raise ValueError("Archive ZIP source size mismatch")
                digest = hashlib.sha256()
                with archive.open(name, "r") as source:
                    for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
                        digest.update(chunk)
                if digest.hexdigest() != entry["sha256"]:
                    raise ValueError("Archive ZIP source digest mismatch")

    def _publish_zip(self, temporary, final):
        _reject_links(temporary)
        _reject_links(final)
        os.link(temporary, final)
        _sync_directory(self.archive_dir)
        os.unlink(temporary)
        _sync_directory(self.archive_dir)

    def _build_zip(self, batch):
        self._validate_sources(batch, exact_tree=batch["kind"] == "background")
        temporary = self.archive_dir / batch["temp_name"]
        _reject_links(temporary)
        if temporary.exists():
            os.unlink(temporary)
        with temporary.open("xb") as output:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                if batch["kind"] == "background":
                    archive.writestr(self._background_root(batch).name + "/", b"")
                    for directory in batch["directories"]:
                        archive.writestr(self._archive_name(batch, directory) + "/", b"")
                for entry in batch["entries"]:
                    archive.write(self._source_path(batch, entry), self._archive_name(batch, entry["path"]))
            output.flush()
            os.fsync(output.fileno())
        self._verify_zip(temporary, batch)
        self._validate_sources(batch, exact_tree=batch["kind"] == "background")
        self._publish_zip(temporary, self.archive_dir / batch["zip_name"])

    def _finish_batch(self, batch):
        temporary = self.archive_dir / batch["temp_name"]
        _reject_links(temporary)
        if temporary.exists():
            os.unlink(temporary)
        os.unlink(self._manifest_path(batch))
        _sync_directory(self.archive_dir)

    def _remove_sources(self, batch, *, staged=False):
        pending = []
        changed = False
        success = not any(entry.get("retained") for entry in batch["entries"])
        for entry in batch["entries"]:
            if entry.get("removed"):
                continue
            source = self._source_path(batch, entry, staged=staged)
            try:
                matches = self._matches(source, entry)
            except FileNotFoundError:
                entry["removed"] = True
                changed = True
                continue
            if matches:
                pending.append(entry)
            else:
                entry["removed"] = True
                entry["retained"] = True
                changed = True
                success = False
                self._report("Changed source retained: " + entry["path"])
        if changed:
            self._write_manifest(batch)
        for entry in pending:
            source = self._source_path(batch, entry, staged=staged)
            try:
                if self._matches(source, entry):
                    os.unlink(source)
                    _sync_directory(source.parent)
                else:
                    entry["retained"] = True
                    success = False
                    self._report("Changed source retained: " + entry["path"])
            except FileNotFoundError:
                pass
            entry["removed"] = True
            self._write_manifest(batch)
        return success

    def _reset_background(self, batch):
        root = self._background_root(batch)
        stage = self._staging_path(batch)
        if batch["state"] == "published":
            self._validate_sources(batch, exact_tree=True)
            if stage.exists():
                raise FileExistsError("Background staging directory already exists")
            batch["state"] = "staging"
            self._write_manifest(batch)
        if batch["state"] == "staging":
            if not stage.exists():
                self._validate_sources(batch, exact_tree=True)
                os.rename(root, stage)
                _sync_directory(root.parent)
            created_root = False
            if not root.exists():
                root.mkdir()
                _sync_directory(root.parent)
                created_root = True
            elif not root.is_dir():
                raise ValueError("Background reset destination is not a directory")
            batch["state"] = "reset"
            self._write_manifest(batch)
            if created_root:
                self.background_reset_completed = True
        success = True
        if stage.exists():
            success = self._remove_sources(batch, staged=True)
            for directory in sorted(batch["directories"], key=lambda value: value.count("/"), reverse=True):
                path = self._source_path(batch, {"path": directory}, staged=True)
                try:
                    os.rmdir(path)
                except FileNotFoundError:
                    pass
            os.rmdir(stage)
            _sync_directory(root.parent)
        if not root.exists():
            root.mkdir()
            _sync_directory(root.parent)
        return success

    def _resume_batch(self, batch):
        final = self.archive_dir / batch["zip_name"]
        _reject_links(final)
        if final.exists():
            self._verify_zip(final, batch)
        else:
            if batch["state"] != "prepared":
                raise ValueError("Committed archive ZIP is missing; sources retained")
            try:
                self._build_zip(batch)
            except _SourceChanged as error:
                # Nothing was published or deleted. A fresh snapshot can be
                # archived later instead of pinning a stale startup batch.
                self._finish_batch(batch)
                self._report("Uncommitted stale batch retired; sources retained: " + str(error))
                return False
        if batch["state"] == "prepared":
            batch["state"] = "published"
            self._write_manifest(batch)
        if batch["kind"] == "background":
            try:
                success = self._reset_background(batch)
            except _SourceChanged as error:
                if (batch["state"] in ("published", "staging")
                        and not self._staging_path(batch).exists()
                        and self._background_root(batch).is_dir()):
                    # A failed directory move left the live root in place.
                    # Retire only its old snapshot, never a detached stage.
                    self._finish_batch(batch)
                    self.background_reset_completed = False
                    self._report("Unstaged stale background batch retired; source retained: " + str(error))
                    return False
                raise
        else:
            success = self._remove_sources(batch)
        self._finish_batch(batch)
        return success

    def _new_batch(self, kind, entries, directories=None):
        self._ensure_archive_dir()
        while True:
            batch_id = uuid.uuid4().hex
            name = kind + "-" + time.strftime("%Y%m%d-%H%M%S") + "-" + batch_id + ".zip"
            batch = {"version": 1, "id": batch_id, "kind": kind, "state": "prepared",
                     "zip_name": name, "temp_name": "." + name + ".tmp", "entries": entries}
            if not self._manifest_path(batch).exists() and not (self.archive_dir / name).exists():
                break
        if kind == "background":
            batch["source_root"] = str(self.background_dir)
            batch["directories"] = directories
        self._write_manifest(batch)
        return self._resume_batch(batch)

    def _recover_kinds(self, kinds):
        try:
            if not self.archive_dir.exists():
                return True
            self._ensure_archive_dir()
            success = True
            for manifest in sorted(self.archive_dir.glob(".batch-*.json")):
                try:
                    # Runtime never validates or acts on startup source paths.
                    if not _is_regular(manifest):
                        raise ValueError("Archive manifest must be a regular file")
                    with manifest.open("r", encoding="utf-8") as source:
                        kind = json.load(source).get("kind")
                    if kind not in ("runtime", "startup", "background"):
                        raise ValueError("Unknown archive batch kind")
                    if kind not in kinds:
                        continue
                    batch = self._read_manifest(manifest)
                    if not self._resume_batch(batch):
                        success = False
                except Exception as error:
                    self._report(error)
                    success = False
            return success
        except Exception as error:
            self._report(error)
            return False

    def recover(self, startup=False):
        with self.lock:
            kinds = {"runtime", "startup", "background"} if startup else {"runtime"}
            return self._recover_kinds(kinds)

    def _check_startup_claims(self, paths):
        for manifest in self.archive_dir.glob(".batch-*.json"):
            if not _is_regular(manifest):
                raise ValueError("Archive manifest must be a regular file")
            with manifest.open("r", encoding="utf-8") as source:
                kind = json.load(source).get("kind")
            if kind == "startup":
                batch = self._read_manifest(manifest)
                claimed = {self._source_path(batch, entry) for entry in batch["entries"]
                           if not entry.get("removed")}
                if claimed.intersection(paths):
                    raise ValueError("Numbered logs belong to a pending startup archive")

    def archive_runtime(self, paths):
        with self.lock:
            try:
                validated = []
                for value in paths:
                    path = _absolute(value)
                    if path.parent != self.log_dir or not _NUMBERED_LOG.fullmatch(path.name):
                        raise ValueError("Runtime archive accepts numbered files in the log directory only")
                    _reject_links(path)
                    if path not in validated:
                        validated.append(path)
                if not self.recover(startup=False):
                    return False
                self._check_startup_claims(validated)
                entries = []
                for path in validated:
                    if path.exists():
                        entries.append({"path": path.name, **self._fingerprint(path)})
                if entries:
                    success = self._new_batch("runtime", entries)
                else:
                    success = True
                self.cleanup()
                return success
            except Exception as error:
                self._report(error)
                return False

    def archive_startup_logs(self):
        with self.lock:
            try:
                if not self._recover_kinds({"runtime", "startup"}):
                    return False
                _reject_links(self.log_dir)
                if not self.log_dir.exists():
                    return True
                entries = []
                for path in sorted(self.log_dir.iterdir()):
                    if path.name in _ACTIVE_LOGS or _NUMBERED_LOG.fullmatch(path.name):
                        entries.append({"path": path.name, **self._fingerprint(path)})
                if entries:
                    success = self._new_batch("startup", entries)
                else:
                    success = True
                self.cleanup()
                return success
            except Exception as error:
                self._report(error)
                return False

    def archive_startup_background(self, background_dir):
        with self.lock:
            self.background_reset_completed = False
            try:
                root = _absolute(background_dir)
                if self.background_dir is None:
                    self.background_dir = root
                if root != self.background_dir:
                    raise ValueError("Background source differs from its configured directory")
                self._background_root({"source_root": str(root)})
                if not self._recover_kinds({"background"}):
                    return False
                if not root.exists():
                    root.mkdir(parents=True)
                    return True
                entries, directories = self._scan_background(root)
                if entries or directories:
                    success = self._new_batch("background", entries, directories)
                else:
                    success = True
                self.cleanup()
                return success
            except Exception as error:
                self._report(error)
                return False

    def cleanup(self):
        """Apply the ZIP quota without pruning any unfinished transaction."""
        with self.lock:
            try:
                quota = float(self.max_size_mb)
                if quota <= 0 or not self.archive_dir.exists():
                    return
                self._ensure_archive_dir()
                protected = set()
                for manifest in self.archive_dir.glob(".batch-*.json"):
                    if not _is_regular(manifest):
                        raise ValueError("Unsafe archive manifest prevents quota cleanup")
                    with manifest.open("r", encoding="utf-8") as source:
                        batch = json.load(source)
                    name = batch.get("zip_name")
                    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".zip"):
                        raise ValueError("Unreadable archive transaction prevents quota cleanup")
                    protected.add(name)
                archives = []
                for path in self.archive_dir.glob("*.zip"):
                    if not _is_regular(path):
                        continue
                    metadata = path.stat()
                    archives.append((metadata.st_mtime_ns, path.name, metadata.st_size, path))
                archives.sort()
                if not archives:
                    return
                protected.add(archives[-1][1])
                total = sum(archive[2] for archive in archives)
                for _, name, size, path in archives:
                    if total <= quota * 1024 * 1024:
                        break
                    if name in protected:
                        continue
                    os.unlink(path)
                    _sync_directory(self.archive_dir)
                    total -= size
                if total > quota * 1024 * 1024:
                    self._report("ZIP quota remains exceeded; newest archive and unfinished batches retained")
            except Exception as error:
                self._report(error)
