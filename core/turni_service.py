"""
Modulo di Dominio e Servizio Turni per Kandor ERP.
Centralizza la logica di business relativa a:
- Calcolo e validazione delle ore previste per turno/assegnazione
- Registrazione timbrature Geofence GPS (Check-In / Check-Out) con supporto timestamp offline
- Convalida e salvataggio ore per singoli dipendenti e squadre
"""

import logging
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple

from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger('kandor.turni')


def calcola_ore_previste(assign) -> float:
    """
    Calcola le ore previste da contratto o da orario programmato per un'assegnazione turno.
    Restituisce float per confronti numerici.
    """
    if not assign:
        return 0.0

    # 1. Ore contrattuali esplicite sull'assegnazione
    if getattr(assign, 'ore_previste_contratto', None) and assign.ore_previste_contratto > 0:
        return float(assign.ore_previste_contratto)

    # 2. Orario inizio e fine previsti
    ini = getattr(assign, 'orario_inizio_previsto', None)
    fine = getattr(assign, 'orario_fine_previsto', None)
    if ini and fine:
        dummy_date = date(2000, 1, 1)
        dt_ini = datetime.combine(dummy_date, ini)
        dt_fine = datetime.combine(dummy_date, fine)
        if dt_fine < dt_ini:
            dt_fine += timedelta(days=1)
        diff_h = (dt_fine - dt_ini).total_seconds() / 3600.0
        if diff_h > 0:
            return round(diff_h, 2)

    # 3. Fallback sulla programmazione ricorrente del cliente
    cli = getattr(assign, 'cliente', None)
    turno = getattr(assign, 'turno', None)
    if cli and turno and turno.data:
        giorno_sett = turno.data.weekday()  # 0=Lun, ..., 6=Dom
        prog = cli.programmazioni.filter(giorno_settimana=giorno_sett).first()
        if prog:
            if prog.ore_previste and prog.ore_previste > 0:
                return float(prog.ore_previste)
            if prog.orario_inizio and prog.orario_fine:
                dt_i = datetime.combine(date(2000, 1, 1), prog.orario_inizio)
                dt_f = datetime.combine(date(2000, 1, 1), prog.orario_fine)
                if dt_f < dt_i:
                    dt_f += timedelta(days=1)
                return round((dt_f - dt_i).total_seconds() / 3600.0, 2)

    return 0.0


def registra_timbratura_gps(
    dipendente,
    cliente_id: Optional[int] = None,
    assign_id: Optional[int] = None,
    tipo_timbratura: str = 'CHECK_IN',
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    timestamp_rilevato: Optional[datetime] = None,
    source: str = 'WEBAPP',
) -> Dict[str, Any]:
    """
    Registra un evento di timbratura GPS (CHECK_IN o CHECK_OUT) per un dipendente.
    Supporta timestamp retrodatato nativo per sincronizzazioni da modalità offline.
    """
    from .models import Cliente, Squadra, Turno, AssegnazioneTurno, TimeTracking, ProximityLog

    now = timestamp_rilevato or timezone.now()
    today = timezone.localtime(now).date()
    tipo = tipo_timbratura.strip().upper()

    assign = None
    if assign_id and str(assign_id).isdigit():
        assign = AssegnazioneTurno.objects.select_related('cliente', 'turno').filter(pk=int(assign_id)).first()

    if not assign and cliente_id and str(cliente_id).isdigit():
        assign = (
            AssegnazioneTurno.objects.select_related('cliente', 'turno')
            .filter(cliente_id=int(cliente_id), turno__data=today)
            .filter(
                Q(turno__squadra__componenti=dipendente)
                | Q(turno__squadra__caposquadra=dipendente)
                | Q(timetracks__dipendente=dipendente)
            )
            .first()
        )
        if not assign:
            assign = (
                AssegnazioneTurno.objects.select_related('cliente', 'turno')
                .filter(cliente_id=int(cliente_id), turno__data=today)
                .first()
            )

    # Se non esiste ancora un turno programmato oggi per questo cantiere, crealo al volo
    if not assign and cliente_id and str(cliente_id).isdigit():
        target_cli = Cliente.objects.filter(pk=int(cliente_id)).first()
        if target_cli:
            squadra = dipendente.squadre_appartenenza.first() or dipendente.squadre_capitanate.first()
            if not squadra:
                squadra = Squadra.objects.first()
            turno, _ = Turno.objects.get_or_create(
                data=today,
                squadra=squadra,
            )
            ora_inizio = timezone.localtime(now).time().replace(second=0, microsecond=0)
            dt_fine = datetime.combine(today, ora_inizio) + timedelta(hours=2)
            assign, _ = AssegnazioneTurno.objects.get_or_create(
                turno=turno,
                cliente=target_cli,
                defaults={
                    'orario_inizio_previsto': ora_inizio,
                    'orario_fine_previsto': dt_fine.time(),
                    'ore_previste_contratto': Decimal('2.00'),
                    'mansione_svolta': "Timbratura rapida da App Dipendenti",
                }
            )

    if not assign:
        return {
            'ok': False,
            'error': 'Seleziona un cantiere valido per registrare la timbratura GPS.',
        }

    cliente = assign.cliente
    distanza_m = None
    is_near = True

    try:
        if lat is not None and lon is not None:
            lat_f = float(lat)
            lon_f = float(lon)
            if cliente and cliente.latitudine and cliente.longitudine:
                from geopy.distance import geodesic
                distanza_m = int(round(geodesic((lat_f, lon_f), (cliente.latitudine, cliente.longitudine)).meters))
                is_near = distanza_m <= 300
    except Exception as exc:
        logger.warning(f"Errore calcolo distanza geodetica: {exc}")

    # Aggiorna tracciabilità Geofence
    if cliente:
        try:
            if tipo == 'CHECK_IN':
                ProximityLog.objects.update_or_create(
                    dipendente=dipendente,
                    cliente=cliente,
                    defaults={
                        'is_near': is_near,
                        'entered_at': now,
                        'exited_at': None,
                    },
                )
            else:
                prox_obj, _ = ProximityLog.objects.get_or_create(
                    dipendente=dipendente,
                    cliente=cliente,
                    defaults={'is_near': is_near, 'entered_at': now},
                )
                prox_obj.is_near = False
                prox_obj.exited_at = now
                prox_obj.save()
        except Exception:
            pass

    tt, _ = TimeTracking.objects.get_or_create(
        dipendente=dipendente,
        assegnazione=assign,
        defaults={'source': source},
    )
    if lat is not None and lon is not None:
        tt.latitudine = float(lat)
        tt.longitudine = float(lon)

    ora_locale = timezone.localtime(now).strftime('%H:%M')
    gps_badge = f" (📍 GPS verificato a {distanza_m}m dal cantiere)" if distanza_m is not None else " (📍 Timbratura registrata)"

    if tipo == 'CHECK_IN':
        tt.check_in = now
        tt.source = source
        tt.save()
        return {
            'ok': True,
            'message': f"🟢 Check-In registrato alle {ora_locale} presso {cliente.ragione_sociale}{gps_badge}!",
            'ora': ora_locale,
            'tipo': 'CHECK_IN',
            'distanza_m': distanza_m,
            'is_near': is_near,
            'assign_id': assign.id,
        }
    else:
        tt.check_out = now
        tt.source = source
        if not tt.check_in:
            prev_h = calcola_ore_previste(assign)
            tt.check_in = now - timedelta(hours=float(prev_h or 2.0))
        delta_h = max(0.5, round((tt.check_out - tt.check_in).total_seconds() / 3600.0, 1))
        if tt.ore_dichiarate is None:
            tt.ore_dichiarate = Decimal(str(delta_h))
        nota_gps = f"[Geofence {ora_locale}" + (f" - {distanza_m}m]" if distanza_m is not None else "]")
        if nota_gps not in (tt.note or ''):
            tt.note = ((tt.note or '') + ' ' + nota_gps).strip()
        tt.save()
        try:
            assign.dipendenti_esclusi.remove(dipendente)
        except Exception:
            pass
        return {
            'ok': True,
            'message': f"🔴 Check-Out registrato alle {ora_locale} presso {cliente.ragione_sociale} ({tt.ore_dichiarate}h calcolate){gps_badge}!",
            'ora': ora_locale,
            'tipo': 'CHECK_OUT',
            'ore_calcolate': float(tt.ore_dichiarate),
            'distanza_m': distanza_m,
            'is_near': is_near,
            'assign_id': assign.id,
        }
