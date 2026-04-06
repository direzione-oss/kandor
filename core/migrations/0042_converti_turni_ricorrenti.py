from django.db import migrations
from decimal import Decimal


def converti_turni_in_ricorrenti(apps, schema_editor):
    """
    Converte tutti i turni esistenti senza programmazione_feriale in ricorrenti.
    Su SQLite (sviluppo locale) viene saltata: i dati arrivano già convertiti
    da Supabase tramite loaddata.
    """
    from django.db import connection
    if connection.vendor == 'sqlite':
        print('\n  [SKIP] Data migration saltata su SQLite — i dati arrivano da loaddata.')
        return

    AssegnazioneTurno = apps.get_model('core', 'AssegnazioneTurno')
    ProgrammazioneRicorrente = apps.get_model('core', 'ProgrammazioneRicorrente')

    # Prendi tutte le assegnazioni senza programmazione
    senza_prog = AssegnazioneTurno.objects.filter(
        programmazione_feriale__isnull=True
    ).select_related('turno__squadra', 'cliente', 'turno')

    # Mappa: chiave → ProgrammazioneRicorrente già creata
    prog_map = {}

    for assign in senza_prog:
        turno = assign.turno
        if not turno or not turno.squadra:
            continue

        giorno = turno.data.weekday()  # 0=Lunedì
        key = (
            turno.squadra_id,
            assign.cliente_id,
            giorno,
            assign.orario_inizio_previsto,
        )

        if key not in prog_map:
            # Calcola durata in ore
            t_i = assign.orario_inizio_previsto
            t_f = assign.orario_fine_previsto
            minuti = (t_f.hour * 60 + t_f.minute) - (t_i.hour * 60 + t_i.minute)
            durata = Decimal(str(round(max(minuti, 0) / 60, 2)))

            prog = ProgrammazioneRicorrente.objects.create(
                cliente=assign.cliente,
                squadra_abituale=turno.squadra,
                tipo_ripetizione='SETTIMANALE',
                giorno_settimana=giorno,
                ora_inizio=t_i,
                durata=durata,
                data_inizio_contratto=turno.data,
            )
            prog_map[key] = prog

        assign.programmazione_feriale = prog_map[key]
        assign.save(update_fields=['programmazione_feriale'])

    total = len(prog_map)
    print(f'\n  ✅ Creati {total} ProgrammazioneRicorrente per i turni esistenti.')


def rollback(apps, schema_editor):
    """Non fare nulla in rollback — troppo rischioso rimuovere le programmazioni."""
    pass


class Migration(migrations.Migration):
    """
    Data migration: converte tutti i turni esistenti senza programmazione_feriale
    in turni ricorrenti, creando le relative ProgrammazioneRicorrente settimanali.
    """

    dependencies = [
        ('core', '0041_add_performance_indexes'),
    ]

    operations = [
        migrations.RunPython(converti_turni_in_ricorrenti, rollback),
    ]
