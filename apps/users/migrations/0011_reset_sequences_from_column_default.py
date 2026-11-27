from django.db import migrations
import re

_NEXTVAL_RE = re.compile(r"nextval\('([^']+)'")


def reset_sequences(apps, schema_editor):
    """Reset Postgres sequences to MAX(id)+1, definitively.

    0009 guessed sequence names; 0010 used pg_get_serial_sequence which
    returns NULL when the sequence isn't OWNED BY the column (broken
    ownership link). This version parses the column's actual DEFAULT
    expression (pg_attrdef) for nextval('seq') - the exact sequence
    Postgres invokes on INSERT - plus pg_get_serial_sequence as a
    fallback for IDENTITY columns. No-op on non-Postgres.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    # seq_ref (as used in nextval('...')) -> table name
    targets = {}

    with schema_editor.connection.cursor() as cursor:
        # 1) Serial-style columns: DEFAULT nextval('seq'::regclass)
        cursor.execute(
            """
            SELECT c.relname, pg_get_expr(d.adbin, d.adrelid)
            FROM pg_attrdef d
            JOIN pg_class c ON c.oid = d.adrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a
              ON a.attrelid = d.adrelid AND a.attnum = d.adnum
            WHERE a.attname = 'id'
              AND c.relkind IN ('r', 'p')
              AND n.nspname = current_schema()
            """
        )
        for table, expr in cursor.fetchall():
            m = _NEXTVAL_RE.search(expr or '')
            if m:
                targets[m.group(1)] = table

        # 2) IDENTITY columns have no pg_attrdef default; find their
        #    sequences via pg_get_serial_sequence per model table.
        for model in apps.get_models():
            table = model._meta.db_table
            if table in targets.values():
                continue
            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, 'id')",
                [table],
            )
            row = cursor.fetchone()
            if row and row[0]:
                targets.setdefault(row[0], table)

        for seq_ref, table in targets.items():
            # setval(seq, N, false) -> next nextval() returns N.
            # Table name inlined as quoted identifier (Django/DB
            # metadata, not user input); seq_ref stays a bind param.
            cursor.execute(
                f'SELECT setval(%s::regclass, '
                f'COALESCE((SELECT MAX("id") FROM "{table}"), 0) + 1, false)',
                [seq_ref],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_reset_sequences_pg_get_serial'),
    ]

    operations = [
        migrations.RunPython(reset_sequences, migrations.RunPython.noop),
    ]
