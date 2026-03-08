"""Management command per il riepilogo settimanale ai titolari (venerdì 18:00).
Uso: python manage.py riepilogo_settimanale
Trigger automatico: configurare cron-job.org su GET /titolari/riepilogo/?token=SECRET
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Invia il riepilogo settimanale ai titolari via Telegram"

    def handle(self, *args, **options):
        from core.services import notifica_titolari
        from core.models import (
            Dipendente, Turno, AssegnazioneTurno,
            TimeTracking, Assenza, RichiestaSostituzione
        )

        oggi = timezone.now().date()
        # Lunedì della settimana corrente
        lun = oggi - timedelta(days=oggi.weekday())
        ven = lun + timedelta(days=4)

        # --- Dipendenti attivi ---
        n_dipendenti = Dipendente.objects.filter(stato='ATTIVO').count()

        # --- Turni della settimana ---
        turni_settimana = AssegnazioneTurno.objects.filter(
            turno__data__gte=lun, turno__data__lte=ven
        )
        n_turni = turni_settimana.count()
        n_compilati = TimeTracking.objects.filter(
            assegnazione__turno__data__gte=lun,
            assegnazione__turno__data__lte=ven
        ).values('assegnazione').distinct().count()
        n_scoperti = n_turni - n_compilati

        # --- Ore totali registrate ---
        from django.db.models import Sum
        ore_result = TimeTracking.objects.filter(
            timestamp__date__gte=lun, timestamp__date__lte=ven
        ).aggregate(tot=Sum('ore_lavorate'))
        ore_tot = round(ore_result['tot'] or 0, 1)

        # --- Assenze della settimana ---
        from django.db.models import Q
        assenze = Assenza.objects.filter(
            Q(data_inizio__lte=ven) & Q(data_fine__gte=lun)
        )
        n_malattia = assenze.filter(tipo='MALATTIA').count()
        n_ferie = assenze.filter(tipo='FERIE').count()
        n_permesso = assenze.filter(tipo='PERMESSO').count()

        # --- Sostituzioni ---
        sost = RichiestaSostituzione.objects.filter(
            creata_il__date__gte=lun, creata_il__date__lte=ven
        )
        n_sost_ok = sost.filter(stato='COMPLETATA').count()
        n_sost_fail = sost.filter(stato='ANNULLATA').count()

        msg = (
            f"📊 <b>RIEPILOGO SETTIMANA</b>\n"
            f"{lun.strftime('%d/%m')} – {ven.strftime('%d/%m/%Y')}\n\n"
            f"👥 Dipendenti attivi: <b>{n_dipendenti}</b>\n"
            f"📋 Turni: <b>{n_turni}</b> pianificati | <b>{n_compilati}</b> compilati | <b>{n_scoperti}</b> scoperti\n"
            f"⏱ Ore registrate: <b>{ore_tot}h</b>\n"
            f"🔄 Sostituzioni: <b>{n_sost_ok}</b> risolte, <b>{n_sost_fail}</b> fallite\n"
            f"🤒 Assenze: <b>{n_malattia}</b> malattia | <b>{n_ferie}</b> ferie | <b>{n_permesso}</b> permesso\n\n"
            f"🔗 <a href='https://kandor.onrender.com/titolari/'>Apri Dashboard Supervisione</a>"
        )

        notifica_titolari(msg)
        self.stdout.write(self.style.SUCCESS(f"Riepilogo settimanale inviato ({oggi})"))
