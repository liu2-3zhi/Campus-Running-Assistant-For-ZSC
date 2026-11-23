"""Explicit, offline migration between approved files and the MySQL store.

This module deliberately does not import main or install filesystem hooks. Source
files and log paths are never changed by import or verification.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class MigrationError(RuntimeError):
    """A migration cannot safely continue. Messages never contain record bodies."""


class VerificationError(MigrationError):
    pass


@dataclass(frozen=True)
class SourceEntry:
    namespace: str
    key: str
    path: Path
    content: bytes
    mtime_ns: int
    digest: str


@dataclass(frozen=True)
class MigrationPlan:
    entries: tuple[SourceEntry, ...]
    skipped_empty: tuple[tuple[str, str], ...] = ()

    @property
    def total_bytes(self):
        return sum(len(entry.content) for entry in self.entries)


@dataclass(frozen=True)
class VerificationReport:
    expected: int
    actual: int
    missing: tuple[tuple[str, str], ...] = ()
    different: tuple[tuple[str, str], ...] = ()
    extra: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self):
        return not (self.missing or self.different or self.extra)


@dataclass(frozen=True)
class ImportResult:
    imported: int
    unchanged: int
    skipped_conflict: int
    skipped_empty: int
    verification: VerificationReport


@dataclass(frozen=True)
class ExportResult:
    exported: int
    total_bytes: int


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _reject_json_constant(_value):
    raise ValueError("nonfinite JSON number")


def _validate_content(key, content):
    try:
        text = content.decode("utf-8-sig")
        if key.lower().endswith(".json"):
            json.loads(text, parse_constant=_reject_json_constant)
        elif key.lower().endswith(".ini"):
            parser = configparser.RawConfigParser(strict=False)
            parser.read_string(text)
            if not parser.sections():
                raise ValueError("INI without sections")
    except (UnicodeError, ValueError, configparser.Error) as exc:
        raise MigrationError(f"源文件格式无效：{key}（{type(exc).__name__}）") from None


def build_plan(policy, *, skip_empty=False):
    """Validate the entire allowlisted source before opening a database."""
    entries, skipped, seen = [], [], set()
    for original_path in policy.iter_files():
        path = Path(original_path)
        identity = policy.identify(path)
        if identity is None:
            raise MigrationError("存储策略返回了范围外的源文件")
        namespace, key = identity
        if identity in seen:
            raise MigrationError(f"源文件标识重复：{namespace}/{key}")
        seen.add(identity)
        if path.is_symlink():
            raise MigrationError(f"拒绝迁移符号链接：{namespace}/{key}")
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise MigrationError(f"读取过程中源文件发生变化：{namespace}/{key}；请先停止应用")
        if not content.strip():
            if skip_empty:
                skipped.append(identity)
                continue
            raise MigrationError(f"源文件为空：{namespace}/{key}；修复源文件或显式使用 --skip-empty")
        _validate_content(key, content)
        entries.append(SourceEntry(namespace, key, path, content, after.st_mtime_ns, _digest(content)))
    return MigrationPlan(tuple(sorted(entries, key=lambda item: (item.namespace, item.key))), tuple(sorted(skipped)))


def _database_documents(store):
    records = {}
    for namespace in store.namespaces():
        for document in store.list(namespace):
            identity = (document.namespace, document.key)
            if identity in records:
                raise MigrationError("数据库返回了重复文档标识")
            records[identity] = document
    return records


def _verify_plan(plan, store):
    expected = {(entry.namespace, entry.key): entry for entry in plan.entries}
    actual = _database_documents(store)
    missing = tuple(sorted(expected.keys() - actual.keys()))
    extra = tuple(sorted(actual.keys() - expected.keys()))
    different = tuple(sorted(
        identity for identity in expected.keys() & actual.keys()
        if _digest(actual[identity].content) != expected[identity].digest
        or actual[identity].digest != _digest(actual[identity].content)
    ))
    return VerificationReport(len(expected), len(actual), missing, different, extra)


def verify_documents(policy, store, *, skip_empty=False):
    """Compare every managed source with every stored document by SHA256."""
    return _verify_plan(build_plan(policy, skip_empty=skip_empty), store)


def import_documents(policy, store, *, conflict="error", batch_size=100, skip_empty=False):
    """Import without changing originals; commits are resumable, verified batches."""
    if conflict not in {"error", "skip", "overwrite"}:
        raise MigrationError("未知冲突策略")
    if not isinstance(batch_size, int) or batch_size < 1:
        raise MigrationError("batch_size 必须为正整数")
    plan = build_plan(policy, skip_empty=skip_empty)
    pending, unchanged, skipped = [], 0, 0
    for entry in plan.entries:
        existing = store.get(entry.namespace, entry.key)
        if existing is not None and _digest(existing.content) == entry.digest and existing.digest == entry.digest:
            unchanged += 1
            continue
        if existing is not None and conflict == "error":
            raise MigrationError(f"目标文档内容冲突：{entry.namespace}/{entry.key}；未开始本轮写入")
        if existing is not None and conflict == "skip":
            skipped += 1
            continue
        pending.append((entry, existing.revision if existing is not None else None))
    store.mark_pending()
    imported = 0
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        with store.transaction():
            for entry, revision in batch:
                options = {"mtime_ns": entry.mtime_ns}
                if revision is None:
                    options["create_only"] = True
                else:
                    options["expected_revision"] = revision
                store.put(entry.namespace, entry.key, entry.content, **options)
        imported += len(batch)
    fresh_plan = build_plan(policy, skip_empty=skip_empty)
    original = {(item.namespace, item.key): (item.digest, item.mtime_ns) for item in plan.entries}
    current = {(item.namespace, item.key): (item.digest, item.mtime_ns) for item in fresh_plan.entries}
    if original != current or plan.skipped_empty != fresh_plan.skipped_empty:
        raise VerificationError("迁移过程中源数据发生变化；未标记就绪，请停止应用后重试")
    with store.transaction():
        verification = _verify_plan(fresh_plan, store)
        if not verification.ok:
            raise VerificationError(
                f"导入后校验失败：缺失 {len(verification.missing)}，不同 {len(verification.different)}，多余 {len(verification.extra)}；未标记就绪"
            )
        store.mark_ready()
    return ImportResult(imported, unchanged, skipped, len(plan.skipped_empty), verification)


def _export_relative_path(policy, document):
    namespace, key = document.namespace, document.key
    if not isinstance(namespace, str) or not isinstance(key, str) or not namespace or not key:
        raise MigrationError("数据库文档标识无效")
    if any(character in key for character in ("\\", ":", "\x00")) or key.startswith("/"):
        raise MigrationError("数据库文档键包含不安全路径")
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(key).is_absolute():
        raise MigrationError("数据库文档键包含不安全路径")
    try:
        physical = Path(policy.physical_path(namespace, key))
        if policy.identify(physical) != (namespace, key):
            raise ValueError("outside policy")
        relative = physical.resolve().relative_to(Path(policy.root).resolve())
    except (ValueError, KeyError, OSError, RuntimeError):
        raise MigrationError("数据库文档不属于受管目录，或自定义目录位于 root 之外；拒绝导出") from None
    return relative


def export_documents(policy, store, target):
    """Export verified bytes into an exclusively-created directory."""
    if store.check_ready() is False:
        raise MigrationError("数据库尚未完成迁移校验")
    target = Path(target).absolute()
    if target.exists() or target.is_symlink():
        raise MigrationError("导出目录必须为全新路径，不覆盖已有目录")
    with store.transaction():
        documents = list(_database_documents(store).values())
        prepared, paths = [], set()
        for document in sorted(documents, key=lambda item: (item.namespace, item.key)):
            relative = _export_relative_path(policy, document)
            if str(relative).casefold() in paths:
                raise MigrationError("导出路径发生大小写或命名冲突")
            paths.add(str(relative).casefold())
            if _digest(document.content) != document.digest:
                raise VerificationError("数据库文档摘要与正文不符，拒绝导出")
            _validate_content(document.key, document.content)
            prepared.append((relative, document))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    for relative, document in prepared:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(document.content)
        os.utime(destination, ns=(document.mtime_ns, document.mtime_ns))
        if _digest(destination.read_bytes()) != document.digest:
            raise VerificationError("导出后文件摘要校验失败；保留现场，未宣称导出成功")
    return ExportResult(len(prepared), sum(len(item.content) for _, item in prepared))


def _parser():
    parser = argparse.ArgumentParser(description="停止应用后显式迁移结构化业务数据；日志和原文件位置保持不变。")
    parser.add_argument("--root", type=Path, default=None, help="数据根目录，默认 APP_STORAGE_ROOT 或项目目录")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="只验证文件并汇总范围，不连接数据库")
    plan.add_argument("--skip-empty", action="store_true")
    commands.add_parser("init", help="显式建立 MySQL 表，不导入数据，不标记就绪")
    importer = commands.add_parser("import", help="导入并核验，成功后标记就绪")
    importer.add_argument("--stopped", action="store_true", required=True, help="确认应用及所有写入进程已停止")
    importer.add_argument("--conflict", choices=("error", "skip", "overwrite"), default="error")
    importer.add_argument("--batch-size", type=int, default=100)
    importer.add_argument("--skip-empty", action="store_true")
    verifier = commands.add_parser("verify", help="核对全部受管记录数量及 SHA256")
    verifier.add_argument("--skip-empty", action="store_true")
    exporter = commands.add_parser("export", help="导出至全新目录，不更改现有文件")
    exporter.add_argument("--output", type=Path, required=True)
    exporter.add_argument("--stopped", action="store_true", required=True)
    return parser


def main(argv=None, *, store_factory=None):
    args = _parser().parse_args(argv)
    try:
        from business_storage import StoragePolicy, StorageSettings
        root = args.root or os.environ.get("APP_STORAGE_ROOT") or Path(__file__).resolve().parent
        policy = StoragePolicy(root)
        if args.command == "plan":
            plan = build_plan(policy, skip_empty=args.skip_empty)
            summary = {"operation": "plan", "records": len(plan.entries), "bytes": plan.total_bytes,
                       "skipped_empty": len(plan.skipped_empty), "by_namespace": dict(Counter(entry.namespace for entry in plan.entries))}
        else:
            if args.command == "import":
                build_plan(policy, skip_empty=args.skip_empty)
            environment = dict(os.environ)
            environment["APP_STORAGE_BACKEND"] = "mysql"
            settings = StorageSettings.from_env(environ=environment, root=root)
            if store_factory is None:
                from business_storage import MySQLDocumentStore
                store_factory = MySQLDocumentStore
            store = store_factory(settings)
            if args.command == "init":
                store.init_schema()
                summary = {"operation": "init", "ok": True, "data_imported": False}
            elif args.command == "import":
                result = import_documents(policy, store, conflict=args.conflict, batch_size=args.batch_size, skip_empty=args.skip_empty)
                summary = {"operation": "import", "ok": True, "imported": result.imported, "unchanged": result.unchanged,
                           "skipped_conflict": result.skipped_conflict, "skipped_empty": result.skipped_empty, "ready": True}
            elif args.command == "verify":
                result = verify_documents(policy, store, skip_empty=args.skip_empty)
                summary = {"operation": "verify", "ok": result.ok, "source_records": result.expected, "database_records": result.actual,
                           "missing": len(result.missing), "different": len(result.different), "extra": len(result.extra)}
                print(json.dumps(summary, ensure_ascii=False))
                return 0 if result.ok else 1
            else:
                result = export_documents(policy, store, args.output)
                summary = {"operation": "export", "ok": True, "exported": result.exported, "bytes": result.total_bytes}
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except MigrationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        # Connection errors can contain passwords or DSNs. Report type only.
        print(json.dumps({"ok": False, "error": f"迁移失败（{type(exc).__name__}）；未输出连接凭据或记录正文"}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
