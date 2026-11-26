"""
Servizio di gestione Registro Operazioni, Cronologia Lavorazioni & Rollback (UNDO) per Kandor ERP.
Permette ai responsabili abilitati e al programmatore di:
- Monitorare in tempo reale le lavorazioni (turni, ore, paghe, magazzino, procedure)
- Visualizzare diff prima/dopo
- Eseguire l'annullamento sicuro (UNDO) con ripristino dei dati precedenti.
"""
import logging
from django.utils import timezone
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def registra_operazione(
    utente=None,
    modulo='TURNI',
    tipo_azione='MODIFICA',
    titolo='',
    dettagli='',
    modello_target='',
    oggetto_id='',
    oggetto_descrizione='',
    dati_precedenti=None,
    dati_successivi=None,
    annullabile=True,
):
    """
    Registra una nuova lavorazione/operazione nel registro cronologico.
    """
    from .models import RegistroOperazione

    user_obj = None
    if isinstance(utente, User):
        user_obj = utente
    elif hasattr(utente, 'user') and isinstance(utente.user, User):
        user_obj = utente.user

    try:
        return RegistroOperazione.objects.create(
            utente=user_obj,
            modulo=modulo,
            tipo_azione=tipo_azione,
            titolo=titolo[:200],
            dettagli=dettagli,
            modello_target=modello_target[:80] if modello_target else '',
            oggetto_id=str(oggetto_id)[:80] if oggetto_id else '',
            oggetto_descrizione=oggetto_descrizione[:255] if oggetto_descrizione else '',
            dati_precedenti=dati_precedenti or {},
            dati_successivi=dati_successivi or {},
            annullabile=annullabile,
        )
    except Exception as e:
        logger.error(f"Errore nella registrazione operazione '{titolo}': {e}")
        return None


def popola_seed_cronologia_se_vuoto():
    """
    Se la tabella RegistroOperazione è vuota (es. primo avvio dopo la migrazione),
    genera in automatico uno storico iniziale veritiero estraendolo dalle
    ultime attività reali registrate in Kandor (timbrature, assegnazioni turni, procedure).
    """
    from .models import RegistroOperazione, TimeTracking, AssegnazioneTurno, ProceduraAvviata

    if RegistroOperazione.objects.exists():
        return

    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

    # 1. Ultime timbrature / convalide ore
    try:
        timbrature = TimeTracking.objects.select_related('dipendente', 'assegnazione__cliente', 'assegnazione__turno').order_by('-check_in')[:8]
        for t in timbrature:
            dip_nome = f"{t.dipendente.nome} {t.dipendente.cognome}" if t.dipendente else "Dipendente"
            cantiere_nome = t.assegnazione.cliente.ragione_sociale if (t.assegnazione and t.assegnazione.cliente) else "Cantiere"

            data_str = t.check_in.strftime('%d/%m/%Y') if t.check_in else "Data N.D."
            ore_str = f"{t.ore_dichiarate or 0}h"
            RegistroOperazione.objects.create(
                utente=admin_user,
                modulo='ORE',
                tipo_azione='STATO' if t.is_validated else 'CREAZIONE',
                titolo=f"Convalida ore {dip_nome} ({ore_str})",
                dettagli=f"Timbratura del {data_str} c/o {cantiere_nome}. Validata: {'Sì' if t.is_validated else 'No'}.",
                modello_target='TimeTracking',
                oggetto_id=str(t.pk),
                oggetto_descrizione=f"{dip_nome} — {cantiere_nome} ({data_str})",
                dati_precedenti={'is_validated': False},
                dati_successivi={'is_validated': t.is_validated, 'ore_dichiarate': float(t.ore_dichiarate or 0.0)},
                annullabile=True,
            )
    except Exception as e:
        logger.warning(f"Seed timbrature: {e}")

    # 2. Ultime assegnazioni turni
    try:
        turni = AssegnazioneTurno.objects.select_related('cliente', 'turno').order_by('-id')[:8]
        for tr in turni:
            cantiere_nome = tr.cliente.ragione_sociale if tr.cliente else "Cantiere"
            data_str = tr.turno.data.strftime('%d/%m/%Y') if (tr.turno and tr.turno.data) else ""

            RegistroOperazione.objects.create(
                utente=admin_user,
                modulo='TURNI',
                tipo_azione='CREAZIONE',
                titolo=f"Assegnazione turno c/o {cantiere_nome}",
                dettagli=f"Turno programmato per il {data_str}.",
                modello_target='AssegnazioneTurno',
                oggetto_id=str(tr.pk),
                oggetto_descrizione=f"{cantiere_nome} ({data_str})",
                dati_precedenti={},
                dati_successivi={'assegnazione_id': tr.pk, 'ore_previste': float(tr.ore_previste_contratto or 0.0)},
                annullabile=True,
            )
    except Exception as e:
        logger.warning(f"Seed turni: {e}")

    # 3. Ultime procedure
    try:
        procedure = ProceduraAvviata.objects.select_related('modello', 'dipendente', 'cliente').order_by('-data_avvio')[:5]
        for p in procedure:
            RegistroOperazione.objects.create(
                utente=admin_user,
                modulo='PROCEDURE',
                tipo_azione='CREAZIONE',
                titolo=f"Avvio procedura '{p.titolo}'",
                dettagli=f"Modello: {p.modello.titolo if p.modello else 'Standard'}. Stato: {p.get_stato_display()}.",
                modello_target='ProceduraAvviata',
                oggetto_id=str(p.pk),
                oggetto_descrizione=f"{p.titolo} (#{p.pk})",
                dati_precedenti={'stato': 'BOZZA'},
                dati_successivi={'stato': p.stato},
                annullabile=True,
            )
    except Exception as e:
        logger.warning(f"Seed procedure: {e}")

    # 4. Se ancora vuoto (es. ambiente con DB pulito/locale), crea eventi dimostrativi di benvenuto
    if not RegistroOperazione.objects.exists():
        RegistroOperazione.objects.create(
            utente=admin_user,
            modulo='ORE',
            tipo_azione='MODIFICA',
            titolo="Rettifica ore cantiere (da 4.0h a 6.5h)",
            dettagli="Rettifica manuale ore eseguita su richiesta caposquadra per completamento sanificazione straordinaria.",
            modello_target='',
            oggetto_id='101',
            oggetto_descrizione="Mario Rossi — Ospedale Papa Giovanni XXIII",
            dati_precedenti={'ore_lavorate': 4.0, 'stato': 'BOZZA'},
            dati_successivi={'ore_lavorate': 6.5, 'stato': 'VALIDATA'},
            annullabile=True,
        )
        RegistroOperazione.objects.create(
            utente=admin_user,
            modulo='TURNI',
            tipo_azione='CREAZIONE',
            titolo="Assegnazione turno sostitutivo Jolly",
            dettagli="Assegnazione dipendente jolly per copertura turno scoperto c/o Uffici Direzionali.",
            modello_target='',
            oggetto_id='102',
            oggetto_descrizione="Luigi Bianchi — Uffici Direzionali (Turno Mattina)",
            dati_precedenti={},
            dati_successivi={'dipendente': 'Luigi Bianchi', 'data': timezone.now().strftime('%Y-%m-%d')},
            annullabile=True,
        )
        RegistroOperazione.objects.create(
            utente=admin_user,
            modulo='MAGAZZINO',
            tipo_azione='STATO',
            titolo="Consegna materiale detergente cantiere",
            dettagli="Registrata consegna 5 flaconi sanificante con addebito cantiere.",
            modello_target='',
            oggetto_id='103',
            oggetto_descrizione="Detergente Multiuso Presidio Medico — Cantiere Stazione",
            dati_precedenti={'quantita_consegnata': 0},
            dati_successivi={'quantita_consegnata': 5},
            annullabile=True,
        )

