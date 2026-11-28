from django.db import migrations
import re

_NEXTVAL_RE = re.compile(r"nextval\('([^']+)'")


def reset_sequences(apps, schema_editor):
    """Reset Postgres sequences to MAX(id)+1, definitively.

    Parses each id column's actual DEFAULT expression (pg_attrdef)
    for nextval('seq') - the exact sequence Postgres invokes on INSERT -
    with pg_get_serial_sequence as fallback for IDENTITY columns.
    All table references are schema-qualified to avoid search_path
    ambiguity when duplicate table names exist across schemas.
    No-op on non-Postgres.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    # (schema, table) -> seq_ref (as written inside nextval('...'))
    targets = {}

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        current_schema = cursor.fetchone()[0]

        # 1) Serial-style columns: DEFAULT nextval('seq'::regclass)
        cursor.execute(
            """
            SELECT n.nspname, c.relname, pg_get_expr(d.adbin, d.adrelid)
            FROM pg_attrdef d
            JOIN pg_class c ON c.oid = d.adrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a
              ON a.attrelid = d.adrelid AND a.attnum = d.adnum
            WHERE a.attname = 'id'
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND c.relkind IN ('r', 'p')
              AND n.nspname = current_schema()
            """
        )
        for schema, table, expr in cursor.fetchall():
            m = _NEXTVAL_RE.search(expr or '')
            if m:
                targets[(schema, table)] = m.group(1)

        # 2) IDENTITY columns have no pg_attrdef default; find their
        #    sequences via pg_get_serial_sequence per model table.
        #    Only models whose PK column is actually 'id' - the function
        #    RAISES UndefinedColumn for missing columns (e.g. django_session
        #    whose PK is session_key), which would abort the transaction.
        for model in apps.get_models():
            pk = model._meta.pk
            if pk is None or pk.column != 'id':
                continue
            table = model._meta.db_table
            if (current_schema, table) in targets:
                continue
            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, 'id')",
                [f'{current_schema}.{table}'],
            )
            row = cursor.fetchone()
            if row and row[0]:
                targets.setdefault((current_schema, table), row[0])

        for (schema, table), seq_ref in targets.items():
            # setval(seq, N, false) -> next nextval() returns N.
            # N = MAX(id)+1 (or 1 for empty tables). Identifiers are
            # inlined quoted (catalog metadata, not user input);
            # seq_ref stays a bind param -> 'name'::regclass.
            cursor.execute(
                f'SELECT setval(%s::regclass, COALESCE((SELECT MAX("id") '
                f'FROM "{schema}"."{table}"), 0) + 1, false)',
                [seq_ref],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_reset_sequences_pg_get_serial'),
    ]

    operations = [
        migrations.RunPython(reset_sequences, migrations.RunPython.noop),
    ]
