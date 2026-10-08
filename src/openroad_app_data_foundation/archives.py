"""Explicit read-only historical stores, with all writes owned by the primary DB.

Temporary read views expose immutable snapshot collections without copying a
large database or giving the service permission to mutate an archive.
"""
from pathlib import Path

from openroad_platform_contracts import ContractError

TABLES = ('snapshots', 'records', 'imported_artifacts', 'fragment_sources')


def attach_archives(connection, primary_path, paths):
    primary = Path(primary_path).resolve()
    sources = [Path(path).expanduser().resolve() for path in paths]
    if len(set(sources)) != len(sources) or primary in sources:
        raise ContractError('archive paths must be distinct from each other and the primary database')
    for index, path in enumerate(sources):
        alias = 'archive' + str(index)
        connection.execute('ATTACH DATABASE ? AS ' + alias, (path.as_uri() + '?mode=ro',))
        for table in TABLES:
            expected = [(row['name'], row['type']) for row in connection.execute('PRAGMA main.table_info(' + table + ')')]
            actual = [(row['name'], row['type']) for row in connection.execute('PRAGMA ' + alias + '.table_info(' + table + ')')]
            if actual != expected or not expected:
                raise ContractError('archive schema differs for ' + table)
        # Snapshot-local identities cannot be shadowed across databases.
        for previous in ['main'] + ['archive' + str(i) for i in range(index)]:
            collision = connection.execute('SELECT snapshot_id FROM ' + alias + '.snapshots '
                'WHERE snapshot_id IN (SELECT snapshot_id FROM ' + previous + '.snapshots) LIMIT 1').fetchone()
            if collision:
                raise ContractError('snapshot identity occurs in multiple databases: ' + collision['snapshot_id'])
    if sources:
        aliases = ['main'] + ['archive' + str(i) for i in range(len(sources))]
        for table in ('snapshots', 'imported_artifacts'):
            connection.execute('CREATE TEMP VIEW ' + table + ' AS ' +
                ' UNION ALL '.join('SELECT * FROM ' + alias + '.' + table for alias in aliases))
    return tuple(str(path) for path in sources)
