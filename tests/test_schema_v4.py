import os

import pytest
from sqlalchemy import JSON, inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from persistence.engine import Database, DatabaseError, DatabaseSettings
from persistence.schema_v4 import create_schema_v4, make_schema_v4
from tools.init_database_v4 import main as initialize


@pytest.fixture(params=['sqlite', 'mysql'])
def v4_database(tmp_path, request):
    backend = request.param
    if backend == 'mysql':
        port = os.environ.get('STORAGE_IO_TEST_MYSQL_PORT')
        if not port:
            pytest.skip('Set STORAGE_IO_TEST_MYSQL_PORT for an empty isolated database')
        settings = DatabaseSettings(
            backend='mysql', root=tmp_path, port=port,
            host=os.environ.get('STORAGE_IO_TEST_MYSQL_HOST', '127.0.0.1'),
            user=os.environ.get('STORAGE_IO_TEST_MYSQL_USER', 'root'),
            password=os.environ.get('STORAGE_IO_TEST_MYSQL_PASSWORD', ''),
            database=os.environ['STORAGE_IO_TEST_MYSQL_DATABASE'],
        )
    else:
        settings = DatabaseSettings(root=tmp_path, sqlite_path=':memory:')
    database = Database(settings)
    try:
        with database.connection() as connection:
            metadata = create_schema_v4(connection)
        try:
            yield database, metadata.tables
        finally:
            with database.connection() as connection:
                metadata.drop_all(connection)
    finally:
        database.dispose()


def test_v4_creates_only_business_key_tables(v4_database):
    database, tables = v4_database
    with database.connection() as connection:
        assert set(inspect(connection).get_table_names()) == set(tables)
        assert connection.scalar(select(tables['schema_migrations'].c.version)) == 4
    assert all('document_id' not in table.c and 'row_id' not in table.c for table in tables.values())
    assert 'storage_documents' not in tables
    with pytest.raises(DatabaseError, match='empty database'):
        with database.connection() as connection:
            create_schema_v4(connection)


def test_binding_updates_only_one_pair_and_preserves_exact_identifiers(v4_database):
    database, tables = v4_database
    accounts = tables['system_accounts']
    schools = tables['school_accounts']
    links = tables['account_school_links']
    with database.connection() as connection:
        for key in ('Owner', 'owner', 'owner '):
            connection.execute(accounts.insert().values(auth_username=key, password_hash='test-hash'))
        assert len(set(connection.scalars(select(accounts.c.auth_username)))) == 3
        owner = connection.scalar(select(accounts.c.id).where(accounts.c.auth_username == 'Owner'))
        for number in ('0001', '0002'):
            school_id = connection.execute(schools.insert().values(school_username=number)).inserted_primary_key[0]
            connection.execute(links.insert().values(system_account_id=owner, school_account_id=school_id, device_ua=number))
        target = connection.scalar(select(schools.c.id).where(schools.c.school_username == '0001'))
        binding = links.c.system_account_id == owner, links.c.school_account_id == target
        conditional_update = links.update().where(*binding, links.c.revision == 1).values(device_ua='new UA', revision=2)
        assert connection.execute(conditional_update).rowcount == 1
        assert connection.execute(conditional_update).rowcount == 0
        assert {tuple(row) for row in connection.execute(select(links.c.device_ua, links.c.revision))} == {
            ('new UA', 2), ('0002', 1),
        }


def test_financial_and_audit_history_survives_account_deletion(v4_database):
    database, tables = v4_database
    accounts, schools = tables['system_accounts'], tables['school_accounts']
    links, bills = tables['account_school_links'], tables['billing_records']
    orders, order_bills, refunds = (tables[name] for name in ('payment_orders', 'payment_order_bills', 'payment_refunds'))
    sms = tables['sms_records']
    with database.connection() as connection:
        owner = connection.execute(accounts.insert().values(auth_username='owner', password_hash='hash')).inserted_primary_key[0]
        school = connection.execute(schools.insert().values(school_username='0012')).inserted_primary_key[0]
        connection.execute(links.insert().values(system_account_id=owner, school_account_id=school))
        bill = connection.execute(bills.insert().values(
            school_account_id=school, billing_id='bill', system_account_id=owner,
            auth_username='owner', amount_minor=1299, status='paid',
        )).inserted_primary_key[0]
        order = connection.execute(orders.insert().values(
            order_id='merchant-order', system_account_id=owner, auth_username='owner', amount_minor=1299, status='paid',
        )).inserted_primary_key[0]
        connection.execute(order_bills.insert().values(payment_order_id=order, billing_record_id=bill))
        connection.execute(refunds.insert().values(payment_order_id=order, sequence=0, amount_minor=199))
        connection.execute(sms.insert().values(record_key='audit', system_account_id=owner, auth_username='owner'))
        connection.execute(accounts.delete().where(accounts.c.id == owner))
        assert connection.execute(select(links)).first() is None
        assert tuple(connection.execute(select(bills.c.system_account_id, bills.c.amount_minor)).one()) == (None, 1299)
        assert tuple(connection.execute(select(orders.c.system_account_id, orders.c.amount_minor)).one()) == (None, 1299)
        assert tuple(connection.execute(select(sms.c.system_account_id, sms.c.auth_username)).one()) == (None, 'owner')
        assert connection.scalar(select(refunds.c.amount_minor)) == 199

    with pytest.raises(IntegrityError):
        with database.connection() as connection:
            connection.execute(schools.delete().where(schools.c.id == school))


def test_settings_distinguish_blank_text_json_null_and_absence(v4_database):
    database, tables = v4_database
    settings = tables['system_settings']
    with database.connection() as connection:
        connection.execute(settings.insert().values(scope='proxy', setting_key='trusted_ips', value_kind='text', value_text=''))
        connection.execute(settings.insert().values(scope='demo', setting_key='null', value_kind='json', value_json=JSON.NULL))
        assert connection.scalar(select(settings.c.value_text).where(settings.c.scope == 'proxy')) == ''
        assert connection.scalar(select(settings.c.value_kind).where(settings.c.scope == 'demo')) == 'json'
        assert connection.execute(select(settings).where(settings.c.scope == 'missing')).first() is None

    with pytest.raises(DBAPIError, match='ck_system_settings_value'):
        with database.connection() as connection:
            connection.execute(settings.insert().values(scope='bad', setting_key='invalid', value_kind='text'))


def test_typed_schema_tool_requires_a_new_sqlite_target(tmp_path, capsys):
    target = tmp_path / 'validation.sqlite3'
    assert initialize(['--sqlite-path', str(target)]) == 0
    assert '"created": true' in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        initialize(['--sqlite-path', str(target)])
    assert error.value.code == 1
    database = Database(DatabaseSettings(sqlite_path=target))
    try:
        assert set(inspect(database.engine).get_table_names()) == set(make_schema_v4().tables)
    finally:
        database.dispose()
