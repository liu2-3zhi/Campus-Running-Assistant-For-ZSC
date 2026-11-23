"""Relational mappings for financial, task, content, background and setting data.

Core values live in typed columns. Compatibility layouts reference rows instead
of retaining a second copy of their source document. Provider-specific fields
remain in each entity's extension object and retain their original types.
"""
from __future__ import annotations

from pathlib import PurePosixPath


TABLES = {
    'payment_orders': {
        'order_id': 'text', 'auth_username': 'text', 'username': 'text',
        'amount_minor': 'money', 'refund_total_minor': 'money', 'status': 'text',
        'pay_type': 'text', 'payment_type': 'text', 'trade_no': 'text',
        'product_name': 'text', 'total_count': 'int', 'created_at': 'text',
        'paid_at': 'text', 'paid_time': 'text', 'expires_at': 'text',
        'closed_at': 'text', 'billing_scope': 'json',
    },
    'billing_records': {
        'billing_id': 'text', 'school_username': 'text', 'auth_username': 'text',
        'amount_minor': 'money', 'reason': 'text', 'status': 'text',
        'created_at': 'text', 'updated_at': 'text', 'paid_at': 'text',
        'paid_by': 'text', 'final_payment_order': 'text',
        'admin_cleared_at': 'text', 'admin_cleared_by': 'text',
        'legacy_location': 'text',
    },
    'payment_order_bills': {
        'order_row_id': 'text', 'billing_row_id': 'text', 'order_id': 'text',
        'billing_id': 'text', 'school_username': 'text', 'school_id': 'text',
        'amount_minor': 'money', 'quantity': 'int', 'relation_source': 'text',
    },
    'payment_refunds': {
        'order_row_id': 'text', 'order_id': 'text', 'refund_id': 'text',
        'refund_no': 'text', 'out_request_no': 'text', 'refund_trade_no': 'text',
        'amount_minor': 'money', 'refund_time': 'text', 'created_at': 'text',
        'operator': 'text', 'status': 'text',
    },
    'background_task_states': {
        'session_id': 'text', 'execution_id': 'text', 'status': 'text',
        'total_tasks': 'int', 'completed_tasks': 'int', 'current_task_index': 'int',
        'auto_generate': 'bool', 'map_provider': 'text', 'start_time': 'float',
        'last_update': 'float', 'progress_percent': 'float',
        'current_task_progress': 'float', 'processed_points': 'int',
        'total_points': 'int',
    },
    'background_task_items': {
        'task_row_id': 'text', 'session_id': 'text', 'execution_id': 'text',
        'task_index': 'int', 'position': 'int',
    },
    'messages': {
        'message_id': 'text', 'content': 'text', 'auth_username': 'text',
        'nickname': 'text', 'email': 'text', 'is_guest': 'bool',
        'timestamp': 'text', 'ip': 'text',
    },
    'reminders': {
        'reminder_id': 'text', 'title': 'text', 'message': 'text',
        'start_time': 'text', 'end_time': 'text', 'enabled': 'bool',
        'allow_guest_view': 'bool', 'created_at': 'text', 'updated_at': 'text',
    },
    'background_state_meta': {'schema_version': 'int', 'next_revision': 'int'},
    'background_assignments': {
        'assignment_id': 'text', 'target': 'text', 'image_url': 'text',
        'state': 'text', 'created_at': 'text', 'expires_at': 'text',
    },
    'background_bundles': {
        'bundle_id': 'text', 'pc_assignment_id': 'text',
        'mobile_assignment_id': 'text', 'pc_assignment_row_id': 'text',
        'mobile_assignment_row_id': 'text', 'state': 'text', 'source': 'text',
        'created_at': 'text', 'consumed_at': 'text', 'revision': 'int',
    },
    'background_bindings': {
        'binding_kind': 'text', 'binding_key': 'text', 'bundle_id': 'text',
        'bundle_row_id': 'text', 'bound_at': 'text', 'source': 'text',
        'created_at': 'text', 'expires_at': 'text',
    },
    'application_settings': {
        'category': 'text', 'document_key': 'text', 'section': 'text',
        'setting_key': 'text', 'path': 'json', 'value': 'json',
    },
}


INDEXES = [
    ('payment_orders', ('order_id',), False),
    ('payment_orders', ('auth_username', 'created_at'), False),
    ('payment_orders', ('username', 'created_at'), False),
    ('payment_orders', ('status', 'expires_at'), False),
    ('payment_orders', ('trade_no',), False),
    ('billing_records', ('school_username', 'status', 'created_at'), False),
    ('billing_records', ('billing_id',), False),
    ('payment_order_bills', ('order_row_id',), False),
    ('payment_order_bills', ('billing_row_id',), False),
    ('payment_order_bills', ('billing_id', 'order_id'), False),
    ('payment_refunds', ('order_row_id',), False),
    ('payment_refunds', ('refund_no',), False),
    ('background_task_states', ('session_id', 'execution_id'), False),
    ('background_task_states', ('status', 'last_update'), False),
    ('background_task_items', ('task_row_id', 'position'), False),
    ('messages', ('auth_username', 'timestamp'), False),
    ('reminders', ('enabled', 'start_time', 'end_time'), False),
    ('background_assignments', ('assignment_id',), False),
    ('background_bundles', ('bundle_id',), False),
    ('background_bindings', ('binding_kind', 'binding_key'), False),
    ('background_bindings', ('bundle_id',), False),
    ('application_settings', ('category', 'document_key', 'section'), False),
]


def _record(builder, table, value, fields=None, **constants):
    """Explicit kinds also allow stand-alone Builder use in codec contracts."""
    fields = fields or {name: name for name in TABLES[table] if name in value}
    typed = {source: (column, TABLES[table][column]) for source, column in fields.items()}
    return builder.record(table, value, typed, **constants)


def _replace(builder, table, reference, source_field, tree):
    row = next(row for row in builder.rows[table] if row['row_id'] == reference.row_id)
    # Extras use the same tagged layout as root containers. Replace the source
    # subtree rather than retaining its original value alongside child rows.
    for pair in row['extra'][1]:
        if pair[0] == source_field:
            pair[1] = builder.finish(tree)
            return
    raise ValueError('The child collection must be an existing extension field')


def _dict_items(builder, table, values, fields=None, **constants):
    return [_record(builder, table, item, fields, **constants) if isinstance(item, dict) else item
            for item in values]


def _order(builder, value):
    reference = _record(builder, 'payment_orders', value, {
        **{name: name for name in TABLES['payment_orders']
           if name not in {'amount_minor', 'refund_total_minor'}},
        'amount': 'amount_minor', 'refund_total': 'refund_total_minor',
    })
    items = value.get('billing_items')
    if isinstance(items, list):
        tree = _dict_items(builder, 'payment_order_bills', items, {
            'billing_id': 'billing_id', 'school_username': 'school_username',
            'school_id': 'school_id', 'amount': 'amount_minor', 'quantity': 'quantity',
        }, order_row_id=reference.row_id, order_id=value.get('order_id'),
            relation_source='order_billing_items')
        _replace(builder, 'payment_orders', reference, 'billing_items', tree)
    refunds = value.get('refund_records')
    if isinstance(refunds, list):
        tree = _dict_items(builder, 'payment_refunds', refunds, {
            **{name: name for name in TABLES['payment_refunds']
               if name not in {'order_row_id', 'amount_minor'}},
            'refund_amount': 'amount_minor',
        }, order_row_id=reference.row_id)
        _replace(builder, 'payment_orders', reference, 'refund_records', tree)
    return reference


def _bill(builder, key, value):
    # Keep legacy location as provenance, never infer or overwrite bill ownership.
    location = key.partition('/')[0] if '/' in key else ''
    reference = _record(builder, 'billing_records', value, {
        **{name: name for name in TABLES['billing_records']
           if name not in {'amount_minor', 'legacy_location'}}, 'amount': 'amount_minor',
    }, legacy_location=location)
    orders = value.get('payment_orders')
    if isinstance(orders, list):
        tree = [builder.scalar('payment_order_bills', order, column_name='order_id',
                    kind='text', billing_row_id=reference.row_id,
                    billing_id=value.get('billing_id'), school_username=value.get('school_username'),
                    relation_source='bill_payment_orders')
                if (isinstance(order, (str, int, float)) and not isinstance(order, bool)) or order is None else order
                for order in orders]
        _replace(builder, 'billing_records', reference, 'payment_orders', tree)
    return reference


def _task(builder, value):
    reference = _record(builder, 'background_task_states', value, {
        **{name: name for name in TABLES['background_task_states']
           if name not in {'processed_points', 'total_points'}},
        'singleProcessedPoints': 'processed_points', 'singleTotalPoints': 'total_points',
    })
    indices = value.get('task_indices')
    if isinstance(indices, list):
        tree = [builder.scalar('background_task_items', index, column_name='task_index', kind='int',
                    task_row_id=reference.row_id, session_id=value.get('session_id'),
                    execution_id=value.get('execution_id'), position=position)
                if isinstance(index, int) and not isinstance(index, bool) else index
                for position, index in enumerate(indices)]
        _replace(builder, 'background_task_states', reference, 'task_indices', tree)
    return reference


def _content_list(builder, table, value, envelope):
    fields = {name: name for name in TABLES[table]
              if name not in {'message_id', 'reminder_id'}}
    fields['id'] = 'message_id' if table == 'messages' else 'reminder_id'
    if isinstance(value, list):
        return _dict_items(builder, table, value, fields)
    if isinstance(value, dict) and isinstance(value.get(envelope), list):
        return {**value, envelope: _dict_items(builder, table, value[envelope], fields)}
    return None


def _background(builder, value):
    reference = _record(builder, 'background_state_meta', value)
    assignment_refs, bundle_refs = {}, {}
    assignments = value.get('assignments')
    if isinstance(assignments, dict):
        tree = {}
        for key, assignment in assignments.items():
            if isinstance(assignment, dict):
                child = _record(builder, 'background_assignments', assignment,
                    {name: name for name in TABLES['background_assignments'] if name != 'assignment_id'},
                    assignment_id=key)
                assignment_refs[key] = child
                tree[key] = child
            else:
                tree[key] = assignment
        _replace(builder, 'background_state_meta', reference, 'assignments', tree)
    bundles = value.get('bundles')
    if isinstance(bundles, dict):
        tree = {}
        for key, bundle in bundles.items():
            if isinstance(bundle, dict):
                links = {}
                for source, column in (('pc_assignment_id', 'pc_assignment_row_id'),
                                       ('mobile_assignment_id', 'mobile_assignment_row_id')):
                    target = bundle.get(source)
                    if isinstance(target, str) and target in assignment_refs:
                        links[column] = assignment_refs[target].row_id
                child = _record(builder, 'background_bundles', bundle,
                    {name: name for name in TABLES['background_bundles']
                     if name not in {'bundle_id', 'pc_assignment_row_id', 'mobile_assignment_row_id'}},
                    bundle_id=key, **links)
                bundle_refs[key] = child
                tree[key] = child
            else:
                tree[key] = bundle
        _replace(builder, 'background_state_meta', reference, 'bundles', tree)
    for section in ('identity_bindings', 'guest_bindings', 'auth_claims'):
        bindings = value.get(section)
        if not isinstance(bindings, dict):
            continue
        tree = {}
        for key, binding in bindings.items():
            if not isinstance(binding, dict):
                tree[key] = binding
                continue
            target = binding.get('bundle_id')
            links = {'bundle_row_id': bundle_refs[target].row_id} if isinstance(target, str) and target in bundle_refs else {}
            tree[key] = _record(builder, 'background_bindings', binding,
                {name: name for name in TABLES['background_bindings']
                 if name not in {'binding_kind', 'binding_key', 'bundle_row_id'}},
                binding_kind=section, binding_key=key, **links)
        _replace(builder, 'background_state_meta', reference, section, tree)
    return reference


def _settings(builder, namespace, key, value, path=()):
    if isinstance(value, dict) and value:
        return {name: _settings(builder, namespace, key, child, path + (name,))
                for name, child in value.items()}
    if isinstance(value, list) and value:
        return [_settings(builder, namespace, key, child, path + (position,))
                for position, child in enumerate(value)]
    return builder.scalar('application_settings', value, kind='json', category=namespace,
        document_key=key, section=str(path[0]) if len(path) > 1 else '',
        setting_key=str(path[-1]) if path else '', path=list(path))


def encode(builder, namespace, key, value):
    """Return a relational compatibility tree, or None for another domain."""
    filename = PurePosixPath(key).name
    if filename == '_index.json' or (namespace == 'payment_orders' and filename == 'qr_cache_index.json'):
        return None
    if namespace == 'payment_orders' and isinstance(value, dict):
        return _order(builder, value)
    if namespace == 'billing' and isinstance(value, dict):
        return _bill(builder, key, value)
    if namespace == 'background_tasks' and isinstance(value, dict):
        return _task(builder, value)
    if namespace == 'background_state' and key == 'background_state.json' and isinstance(value, dict):
        return _background(builder, value)
    if namespace == 'settings':
        if key == 'permissions.json':
            return None
        if key in {'messages.json', 'reminders.json'}:
            table = 'messages' if key == 'messages.json' else 'reminders'
            result = _content_list(builder, table, value, table)
            if result is not None:
                return result
        return _settings(builder, namespace, key, value)
    if namespace == 'configs':
        return _settings(builder, namespace, key, value)
    return None
