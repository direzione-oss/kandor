"""
Management command: fast_push
Carica i dati da un file JSON su Supabase usando bulk_create (no loaddata).
Immune al statement_timeout perché usa INSERT batch invece di INSERT singoli.
Il geocoding è saltato automaticamente (SKIP_GEOCODING=1 nell'env).
"""
import json, sys
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Carica dati locali su Supabase via bulk_create (veloce, no timeout)'

    def add_arguments(self, parser):
        parser.add_argument('fixture', help='Path al file JSON da caricare')

    def handle(self, *args, **options):
        fixture_path = options['fixture']

        # Verifica che siamo su PostgreSQL
        if connection.vendor != 'postgresql':
            self.stderr.write(f'ERR: connesso a {connection.vendor}, non PostgreSQL!')
            sys.exit(1)

        with open(fixture_path, encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write(f'INFO: {len(data)} oggetti da caricare su PostgreSQL...')

        from collections import defaultdict
        from django.apps import apps

        by_model = defaultdict(list)
        for obj in data:
            by_model[obj['model']].append(obj)

        MODEL_ORDER = [
            'core.qualifica', 'core.mezzo', 'core.dipendente', 'core.squadra',
            'core.cliente', 'core.programmazionericorrente',
            'core.richiestastraordinaria', 'core.turno', 'core.assegnazioneturno',
            'core.assenza', 'core.timetracking', 'core.responsabilearea',
            'core.richiestasostituzione', 'core.messaggiochat',
            'core.segnalazione', 'core.proximitylog', 'core.messaggioprogrammato',
        ]

        def _fk_m2m(MC):
            fk, m2m = set(), set()
            for fd in MC._meta.get_fields():
                if hasattr(fd, 'many_to_many') and fd.many_to_many:
                    m2m.add(fd.name)
                elif hasattr(fd, 'column') and hasattr(fd, 'related_model') and fd.related_model:
                    fk.add(fd.name)
            return fk, m2m

        total = 0
        for model_label in MODEL_ORDER:
            records = by_model.get(model_label, [])
            if not records:
                continue
            try:
                MC = apps.get_model(*model_label.split('.'))
                fk_names, m2m_names = _fk_m2m(MC)
                instances = []
                for rec in records:
                    kwargs = {'pk': rec['pk']}
                    rec_m2m = {}
                    for k, v in rec['fields'].items():
                        if k in m2m_names:
                            rec_m2m[k] = v
                        elif k in fk_names and v is not None:
                            kwargs[f'{k}_id'] = v
                        else:
                            kwargs[k] = v
                    instances.append((MC(**kwargs), rec_m2m))

                created = MC.objects.bulk_create(
                    [i[0] for i in instances], ignore_conflicts=True
                )
                total += len(created)
                for obj, m2m in instances:
                    for fn, pks in m2m.items():
                        if pks:
                            try:
                                getattr(obj, fn).set(pks)
                            except Exception:
                                pass
            except Exception as e:
                self.stderr.write(f'WARN: {model_label}: {str(e)[:100]}')

        # Reset sequenze PostgreSQL
        seq_tables = [
            'core_turno', 'core_assegnazioneturno', 'core_dipendente',
            'core_cliente', 'core_squadra', 'core_qualifica', 'core_mezzo',
            'core_programmazionericorrente', 'core_assenza', 'core_timetracking',
            'core_responsabilearea', 'core_messaggioprogrammato',
        ]
        with connection.cursor() as cur:
            for tbl in seq_tables:
                try:
                    cur.execute(
                        f"SELECT setval(pg_get_serial_sequence('{tbl}','id'),"
                        f"COALESCE((SELECT MAX(id) FROM {tbl}),1),true);"
                    )
                except Exception:
                    pass

        self.stdout.write(f'FAST_PUSH_OK:{total}')
