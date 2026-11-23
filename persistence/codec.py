"""Lossless JSON shapes around authoritative, typed relational fields.

Layouts contain references and container structure. Entity extras contain only
unmapped extension fields; mapped business fields live in SQL columns.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import math


@dataclass(frozen=True)
class RecordRef:
    table: str
    row_id: str
    projection: str | None = None


def _tree(value):
    if isinstance(value, RecordRef):
        return ['row', value.table, value.row_id, value.projection]
    if isinstance(value, dict):
        return ['dict', [[str(key), _tree(item)] for key, item in value.items()]]
    if isinstance(value, (tuple, list)):
        return ['list', [_tree(item) for item in value]]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Invalid finite number')
        # Native MySQL JSON numbers may round by an ULP when rendered. Exact
        # IEEE representation belongs to the layout, not a JSON double.
        return ['float', value.hex()]
    if isinstance(value, int) and not isinstance(value, bool):
        return ['int', str(value)]
    return ['value', value]


def _typed(value, kind):
    if value is None:
        return None
    if kind == 'json':
        return _tree(value)
    if kind == 'text':
        return str(value)
    if kind == 'money':
        try:
            amount = Decimal(str(value)) * 100
        except (InvalidOperation, ValueError) as exc:
            raise ValueError('Invalid monetary amount') from exc
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise ValueError('Monetary amount must have at most two decimal places')
        return int(amount)
    if kind == 'int':
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError('Invalid integer field')
        return int(number)
    if kind == 'float':
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Invalid finite number')
        exact = Decimal(str(number))
        if exact.as_tuple().exponent < -30 or abs(exact) >= Decimal('1e35'):
            raise ValueError('Numeric business field exceeds exact decimal range')
        return exact
    if kind == 'bool':
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in ('false', '0', 'no', 'off', ''):
                return False
            if lowered in ('true', '1', 'yes', 'on'):
                return True
            raise ValueError('Invalid boolean field')
        return bool(value)
    raise ValueError('Unknown field kind: ' + kind)


def _type(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, str):
        return 'str'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    return 'json'


class Builder:
    def __init__(self, document_id='document', schemas=None):
        self.document_id = document_id
        self.schemas = schemas or {}
        self.rows = defaultdict(list)

    def record(self, table, data, fields=None, **constants):
        if not isinstance(data, dict):
            raise ValueError('An entity record must be an object')
        ordinal = len(self.rows[table])
        row_id = hashlib.sha256(f'{self.document_id}:{table}:{ordinal}'.encode()).hexdigest()
        extra = dict(data)
        row = dict(constants)
        mapped = []
        for source, spec in (fields or {}).items():
            if source not in extra:
                continue
            column, kind = spec if isinstance(spec, (list, tuple)) else (spec, self.schemas.get(table, {}).get(spec, 'text'))
            value = extra.pop(source)
            row[column] = _typed(value, kind)
            info = {'source': source, 'column': column, 'kind': kind, 'type': _type(value)}
            # Representation metadata preserves historical string formatting.
            # Text values themselves are never duplicated in metadata.
            if isinstance(value, str) and kind not in ('text', 'json'):
                info['representation'] = value
            if kind == 'float' and isinstance(value, float) and value == 0 and math.copysign(1, value) < 0:
                info['negative_zero'] = True
            mapped.append(info)
        row.update(row_id=row_id, document_id=self.document_id, ordinal=ordinal, extra=_tree(extra), fields=mapped)
        self.rows[table].append(row)
        return RecordRef(table, row_id)

    def scalar(self, table, value, column_name='value', kind='json', **constants):
        ref = self.record(table, {'value': value}, {'value': (column_name, kind)}, **constants)
        return self.project(ref, 'value')

    @staticmethod
    def project(ref, field):
        return RecordRef(ref.table, ref.row_id, field)

    @staticmethod
    def finish(tree):
        return _tree(tree)


def decode_tree(layout, rows):
    lookup = {(table, row['row_id']): row for table, values in rows.items() for row in values}
    active = set()

    def decode(node):
        tag = node[0]
        if tag == 'float':
            return float.fromhex(node[1])
        if tag == 'int':
            return int(node[1])
        if tag == 'value':
            return node[1]
        if tag == 'dict':
            return {key: decode(value) for key, value in node[1]}
        if tag == 'list':
            return [decode(value) for value in node[1]]
        if tag != 'row':
            raise ValueError('Invalid stored layout')
        identity = (node[1], node[2])
        if identity in active:
            raise ValueError('Cyclic stored entity reference')
        if identity not in lookup:
            raise ValueError('Missing stored entity reference')
        active.add(identity)
        row = lookup[identity]
        result = decode(row['extra'])
        for info in row['fields']:
            value = row.get(info['column'])
            kind, original_type = info['kind'], info['type']
            if value is None:
                value = None
            elif kind == 'json':
                value = decode(value)
            elif 'representation' in info:
                # Use the original representation only while its semantic
                # value still matches the current authoritative column.
                original = info['representation']
                matches = float(_typed(original, kind)) == float(value) if kind == 'float' else _typed(original, kind) == value
                value = original if matches else str(Decimal(value) / 100 if kind == 'money' else value)
            elif kind == 'money':
                value = Decimal(value) / 100
                value = int(value) if original_type == 'int' else float(value)
            elif original_type == 'str':
                value = str(value)
            elif original_type == 'bool':
                value = _typed(value, 'bool')
            elif original_type == 'int':
                value = int(value)
            elif original_type == 'float':
                value = float(value)
                if value == 0 and info.get('negative_zero'):
                    value = -0.0
            result[info['source']] = value
        active.remove(identity)
        return result[node[3]] if len(node) > 3 and node[3] is not None else result

    return decode(layout)
