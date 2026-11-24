"""Build the proposed v4 schema in an explicitly selected, empty database."""
import argparse
import json
import os
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from persistence.engine import Database, DatabaseError, DatabaseSettings
from persistence.schema_v4 import SCHEMA_VERSION, create_schema_v4


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--sqlite-path', type=Path)
    target.add_argument('--mysql-database')
    args = parser.parse_args(argv)

    database = None
    try:
        if args.sqlite_path is not None:
            path = args.sqlite_path.resolve()
            if path.exists():
                raise DatabaseError('Choose a new SQLite file for v4 schema creation')
            settings = DatabaseSettings(sqlite_path=path)
        else:
            environment = dict(os.environ, APP_STORAGE_BACKEND='mysql', MYSQL_DATABASE=args.mysql_database)
            settings = DatabaseSettings.from_env(environ=environment, ignore_table_prefix=True)
        database = Database(settings)
        with database.connection() as connection:
            metadata = create_schema_v4(connection)
    except DatabaseError as error:
        parser.exit(1, f'{error}\n')
    except Exception as error:
        parser.exit(1, f'v4 schema creation failed ({type(error).__name__})\n')
    finally:
        if database is not None:
            database.dispose()
    print(json.dumps({'schema_version': SCHEMA_VERSION, 'tables': len(metadata.tables), 'created': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
