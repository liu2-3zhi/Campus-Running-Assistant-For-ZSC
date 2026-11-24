"""Database SMS audit metadata and read-only import of legacy JSONL history.

Verification codes remain process-local. New audit events intentionally do not
store message content, codes, provider credentials or verification expiry.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
import time
import uuid

from sqlalchemy import select

import storage_io
from persistence.engine import DatabaseError


_LOGGER = logging.getLogger(__name__)
_AUDIT_FIELDS = frozenset({
    'phone', 'scene', 'status', 'provider', 'response_code', 'response_message',
    'timestamp', 'datetime', 'username', 'auth_username', 'source', 'ip', 'session_id',
})


def _timestamp(record):
    try:
        value = float(record.get('timestamp', 0))
        return value if math.isfinite(value) else 0
    except (TypeError, ValueError, OverflowError):
        return 0


class SMSHistoryRepository:
    def __init__(self, store=None):
        if store is None:
            runtime = storage_io.get_runtime()
            if runtime is None:
                raise DatabaseError('SMS audit requires initialized database storage')
            store = runtime.store
        self.store = store

    def append(self, record):
        audit = {name: value for name, value in record.items() if name in _AUDIT_FIELDS}
        audit.setdefault('timestamp', time.time())
        audit.setdefault('datetime', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(audit['timestamp']))))
        audit.setdefault('provider', 'smsbao')
        key = uuid.uuid4().hex + '.json'
        self.store.put('sms_records', key,
            json.dumps(audit, ensure_ascii=False, allow_nan=False).encode('utf-8'), create_only=True)
        return key

    def list(self, *, date='', phone='', limit=100):
        limit = max(0, min(int(limit), 100))
        if not limit:
            return []
        table = getattr(self.store, 'entities', {}).get('sms_records')
        if table is not None and getattr(self.store, 'normalized', False):
            registry = self.store.registry
            query = select(registry).join(table, table.c.document_id == registry.c.document_id).where(
                registry.c.namespace == 'sms_records')
            if date:
                query = query.where(table.c.datetime.startswith(date, autoescape=True))
            if phone:
                query = query.where(table.c.phone.contains(phone, autoescape=True))
            query = query.order_by(table.c.timestamp.desc(), table.c.row_id.desc()).limit(limit)
            with self.store.database.connection() as connection:
                # Filter and cap candidates in SQL before reconstructing their
                # documents; audit history must not decode the entire table.
                documents = self.store._documents(connection, connection.execute(query).mappings())
                return [json.loads(document.content.decode('utf-8-sig')) for document in documents]

        # Compatibility stores and test doubles may expose only list().
        records = []
        for document in self.store.list('sms_records'):
            record = json.loads(document.content.decode('utf-8-sig'))
            if not isinstance(record, dict):
                raise DatabaseError('SMS audit record is not an object')
            if date and not str(record.get('datetime', '')).startswith(date):
                continue
            if phone and phone not in str(record.get('phone', '')):
                continue
            records.append(record)
        records.sort(key=_timestamp, reverse=True)
        return records[:limit]


def record_sms_event(**record):
    """Audit failure cannot turn an already delivered SMS into a send failure."""
    try:
        SMSHistoryRepository().append(record)
        return True
    except Exception as exc:
        _LOGGER.error('[短信历史] 数据库审计记录保存失败 error=%s', exc, exc_info=True)
        return False


def iter_legacy_sms_records(history_path):
    """Yield stable document entries without changing historical field types.

    Duplicate lines are distinct historical events; their line number forms
    part of the key. Rerunning an unchanged/append-only file is idempotent.
    """
    path = Path(history_path)
    mtime_ns = path.stat().st_mtime_ns
    with path.open('r', encoding='utf-8-sig') as handle:
        for number, line in enumerate(handle, 1):
            content = line.strip()
            if not content:
                continue
            try:
                value = json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
                if not isinstance(value, dict):
                    raise ValueError('record is not an object')
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Invalid SMS history at line {number}: {type(exc).__name__}') from None
            identity = hashlib.sha256((str(number) + '\0' + content).encode('utf-8')).hexdigest()
            yield 'legacy_' + identity + '.json', content.encode('utf-8'), mtime_ns
