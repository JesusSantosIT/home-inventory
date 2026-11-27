from django.db import migrations


def reset_sequences(apps, schema_editor):
    """Reset all Postgres sequences to MAX(id)+1.

    Sequences can drift behind the data, causing 'duplicate key value
    violates unique constraint' on the next insert. Uses
    pg_get_serial_sequence so Postgres itself identifies each column's
    owning sequence. No-op on non-Postgres backends.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        for model in apps.get_models():
            pk = model._meta.pk
            if pk is None or pk.column != 'id':
                continue
            table = model._meta.db_table
            # Ask Postgres which sequence owns this column's default
            # (returns schema-qualified name or NULL).
            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, 'id')",
                [table],
            )
            seq = cursor.fetchone()[0]
            if not seq:
                continue
            # setval(seq, N, false) -> next nextval() returns N.
            # N = MAX(id)+1 (or 1 for empty tables). Table name is
            # inlined as a quoted identifier (Django metadata, not
            # user input); seq stays a bind param -> 'name'::regclass.
            cursor.execute(
                f'SELECT setval(%s::regclass, COALESCE((SELECT MAX("id") FROM "{table}"), 0) + 1, false)',
                [seq],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_reset_sequences'),
    ]

    operations = [
        migrations.RunPython(reset_sequences, migrations.RunPython.noop),
    ]
