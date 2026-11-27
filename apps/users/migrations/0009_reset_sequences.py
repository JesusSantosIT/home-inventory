from django.db import migrations


def reset_sequences(apps, schema_editor):
    """Reset all Postgres sequences to MAX(id)+1.

    Sequences can drift behind the data (e.g. rows inserted while a
    sequence wasn't advancing), causing 'duplicate key value violates
    unique constraint' on the next insert. This runs on every deploy via
    the entrypoint's migrate step. No-op on non-Postgres backends.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        # Only touch sequences that actually exist - a bad setval aborts
        # the whole Postgres transaction, so never issue one blindly.
        cursor.execute("SELECT relname FROM pg_class WHERE relkind = 'S'")
        existing = {row[0] for row in cursor.fetchall()}

        for model in apps.get_models():
            pk = model._meta.pk
            if pk is None or pk.column != 'id':
                continue
            table = model._meta.db_table
            seq = f'{table}_id_seq'
            if seq not in existing:
                continue
            # setval(seq, N, false) -> next nextval() returns N.
            # N = MAX(id)+1 (or 1 for empty tables).
            cursor.execute(
                f'SELECT setval(%s, COALESCE((SELECT MAX("id") FROM "{table}"), 0) + 1, false)',
                [seq],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_externalhousehold_remote_api_key_and_more'),
    ]

    operations = [
        migrations.RunPython(reset_sequences, migrations.RunPython.noop),
    ]
