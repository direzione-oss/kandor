
import datetime
import json
import pandas as pd
import io
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from core.models import Dipendente
from core.templatetags.dashboard_extras import upcoming_birthdays_widget

class BirthdayWidgetTestCase(TestCase):
    def test_upcoming_birthdays(self):
        today = timezone.now().date()
        
        # 1. Birthday Today
        d1 = Dipendente.objects.create(
            nome='Today', cognome='Birthday', codice_fiscale='TDBDAY01', 
            stato='ATTIVO', email='a@a.com', telefono='1',
            data_nascita=today.replace(year=1990)
        )
        
        # 2. Birthday in 10 days
        target_date = today + timedelta(days=10)
        d2 = Dipendente.objects.create(
            nome='Future', cognome='Birthday', codice_fiscale='FTBDAY01',
            stato='ATTIVO', email='b@b.com', telefono='2',
            data_nascita=target_date.replace(year=1985)
        )
        
        # 3. Birthday in 25 days (Should NOT show)
        far_date = today + timedelta(days=25)
        d3 = Dipendente.objects.create(
            nome='Far', cognome='Birthday', codice_fiscale='FRBDAY01',
            stato='ATTIVO', email='c@c.com', telefono='3',
            data_nascita=far_date.replace(year=1995)
        )

        # Execute Widget Logic
        context = upcoming_birthdays_widget()
        birthdays = context['employees_birthdays']
        
        # Verify
        self.assertEqual(len(birthdays), 2)
        
        names = [b['obj'].nome for b in birthdays]
        self.assertIn('Today', names)
        self.assertIn('Future', names)
        self.assertNotIn('Far', names)
        
        # Check 'is_today' flag
        today_entry = next(b for b in birthdays if b['obj'].nome == 'Today')
        self.assertTrue(today_entry['is_today'])
        
        future_entry = next(b for b in birthdays if b['obj'].nome == 'Future')
        self.assertFalse(future_entry['is_today'])

    def test_auto_birth_date_from_cf(self):
        # Create user WITHOUT data_nascita, but VALID CF (RSSMRA80A01H501U -> 1980-01-01)
        d = Dipendente.objects.create(
            nome='Mario', cognome='Rossi',
            codice_fiscale='RSSMRA80A01H501U', # 80 = 1980, A = Gen, 01 = 1st
            stato='ATTIVO'
        )
        
        d.refresh_from_db()
        self.assertIsNotNone(d.data_nascita)
        self.assertEqual(d.data_nascita.year, 1980)
        self.assertEqual(d.data_nascita.month, 1)
        self.assertEqual(d.data_nascita.day, 1)

        # Test Female (Day + 40) -> RSSMRA80A41H501U -> 1980-01-01 Woman
        d2 = Dipendente.objects.create(
            nome='Maria', cognome='Rossi',
            codice_fiscale='RSSMRA80A41H501U', 
            stato='ATTIVO'
        )
        d2.refresh_from_db()
        self.assertEqual(d2.data_nascita.day, 1) # 41 - 40 = 1

    def test_leap_year_birthday(self):
        # Create an employee born on February 29th of a leap year (e.g. 1988)
        d = Dipendente.objects.create(
            nome='LeapYear', cognome='Born',
            codice_fiscale='BRNLYR88B29H501A', # 88 = 1988, B = Feb, 29 = 29th
            stato='ATTIVO',
            data_nascita=datetime.date(1988, 2, 29)
        )
        
        # Test widget rendering - it should not crash even if today is a non-leap year (e.g. 2026)
        try:
            context = upcoming_birthdays_widget()
            self.assertIn('employees_birthdays', context)
        except ValueError as e:
            self.fail(f"upcoming_birthdays_widget crashed with leap year birthday: {e}")

class WeeklyScheduleWidgetTestCase(TestCase):
    def test_schedule_generation(self):
        from core.templatetags.dashboard_extras import weekly_schedule_widget
        from core.models import Turno, Squadra, Dipendente, Mezzo, Cliente, AssegnazioneTurno
        import datetime
        
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        
        # Setup Data
        d = Dipendente.objects.create(nome='Capo', cognome='Squadra', codice_fiscale='CAPO01')
        s = Squadra.objects.create(nome='Squadra A', caposquadra=d)
        m = Mezzo.objects.create(targa='TARGA1', modello='Furgone')
        c = Cliente.objects.create(ragione_sociale='Cliente Test', indirizzo_sede='Via Roma', ore_mensili_contratto=10)
        
        # Create Shift on Monday of this week
        t1 = Turno.objects.create(data=start_of_week, squadra=s, mezzo=m)
        AssegnazioneTurno.objects.create(
            turno=t1, cliente=c, 
            orario_inizio_previsto=datetime.time(8,0), 
            orario_fine_previsto=datetime.time(12,0)
        )
        
        # Create Shift on Tuesday
        t2 = Turno.objects.create(data=start_of_week + timedelta(days=1), squadra=s, mezzo=m)
        
        # Run Widget Logic (Mock Context)
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/') # Default week=0
        context = {'request': request}
        
        result_context = weekly_schedule_widget(context)
        schedule = result_context['schedule']
        
        # Verify Structure
        self.assertEqual(len(schedule), 7) # Should be 7 days
        
        # Verify Monday (Index 0)
        mon_entry = schedule[0]
        self.assertEqual(mon_entry['date_obj'], start_of_week)
        # is_today depends on when test runs, so we skip that check or calc dynamically
        self.assertEqual(len(mon_entry['shifts']), 1)
        self.assertEqual(mon_entry['shifts'][0]['squadra'], 'Squadra A')
        
        # Verify Tuesday (Index 1)
        tue_entry = schedule[1]
        self.assertEqual(len(tue_entry['shifts']), 1)
        
        # Verify Wednesday (Index 2 - Empty)
        wed_entry = schedule[2]
        self.assertEqual(len(wed_entry['shifts']), 0)

from core.models import Dipendente, Qualifica
from core.utils_import import import_from_excel, generate_excel_template

class ImportDipendenteTestCase(TestCase):
    def test_import_dipendente_success(self):
        # 1. Generate template
        template_io = generate_excel_template('dipendente')
        
        # 2. Modify template to add data
        # We need to read it back into a dataframe, append data, and write to new buffer
        df = pd.read_excel(template_io)
        
        # New data row
        new_row = {
            'nome': 'Test',
            'cognome': 'User',
            'codice_fiscale': 'TSTSRA80A01H501U',
            'data_nascita': '1990-01-01',
            'stato': 'ATTIVO',
            'email': 'test@example.com',
            'telefono': '1234567890',
            'indirizzo_residenza': 'Via Test 123',
            'qualifiche_nomi': 'Tester, Developer',
            'telegram_chat_id': '987654321'
        }
        
        # Append row
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save to buffer
        import_buffer = io.BytesIO()
        with pd.ExcelWriter(import_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        import_buffer.seek(0)
        
        # 3. Call import function
        count, errors = import_from_excel('dipendente', import_buffer)
        
        # 4. Assertions
        self.assertEqual(count, 1, f"Import count should be 1. Errors: {errors}")
        self.assertEqual(len(errors), 0, f"Errors should be empty. Got: {errors}")
        
        dip = Dipendente.objects.get(codice_fiscale='TSTSRA80A01H501U')
        self.assertEqual(dip.nome, 'Test')
        self.assertEqual(dip.cognome, 'User')
        self.assertEqual(dip.data_nascita, datetime.date(1990, 1, 1))
        self.assertEqual(dip.stato, 'ATTIVO')
        self.assertEqual(dip.email, 'test@example.com')
        self.assertEqual(dip.telefono, '1234567890')
        self.assertEqual(dip.telegram_chat_id, '987654321')
        
        quals = list(dip.qualifiche.values_list('nome', flat=True))
        self.assertIn('Tester', quals)
        self.assertIn('Developer', quals)

    def test_import_dipendente_updates_existing(self):
        # Create existing
        d = Dipendente.objects.create(
            nome='OldName', cognome='OldSurname', 
            codice_fiscale='TSTSRA80A01H501U',
            data_nascita=datetime.date(1980, 1, 1)
        )
        
        # Prepare import data
        data = {
            'nome': 'NewName',
            'cognome': 'NewSurname',
            'codice_fiscale': 'TSTSRA80A01H501U', # Same CF
            'data_nascita': '1990-01-01',
            'indirizzo_residenza': 'Via Test 123',
            'stato': 'MALATTIA',
        }
        
        df = pd.DataFrame([data])
        import_buffer = io.BytesIO()
        with pd.ExcelWriter(import_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        import_buffer.seek(0)
        
        # Mode UPDATE (default)
        count, errors = import_from_excel('dipendente', import_buffer, mode='UPDATE')
        
        self.assertEqual(count, 1)
        
        d.refresh_from_db()
        self.assertEqual(d.nome, 'NewName')
        self.assertEqual(d.stato, 'MALATTIA')

    def test_import_add_only_skips_existing(self):
        # Create existing
        d = Dipendente.objects.create(
            nome='OldName', cognome='OldSurname', 
            codice_fiscale='TSTSRA80A01H501U',
            data_nascita=datetime.date(1980, 1, 1)
        )
        
        # Prepare import data
        data = {
            'nome': 'NewName',
            'cognome': 'NewSurname',
            'codice_fiscale': 'TSTSRA80A01H501U', # Same CF
            'stato': 'MALATTIA',
        }
        
        df = pd.DataFrame([data])
        import_buffer = io.BytesIO()
        with pd.ExcelWriter(import_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        import_buffer.seek(0)
        
        # Mode ADD_ONLY
        count, errors = import_from_excel('dipendente', import_buffer, mode='ADD_ONLY')
        
        self.assertEqual(count, 0) # Should skip
        
        d.refresh_from_db()
        self.assertEqual(d.nome, 'OldName') # Should NOT change

    def test_import_missing_date(self):
        # Prepare import data with NO date
        data = {
            'nome': 'NoDate',
            'cognome': 'User',
            'codice_fiscale': 'NODATE80A01H501U',
            'stato': 'ATTIVO',
        }
        
        df = pd.DataFrame([data])
        import_buffer = io.BytesIO()
        with pd.ExcelWriter(import_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        import_buffer.seek(0)
        
        count, errors = import_from_excel('dipendente', import_buffer)
        
        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 0)
        
        d = Dipendente.objects.get(codice_fiscale='NODATE80A01H501U')
        # Now that we auto-calculate from CF, this should NOT be None anymore!
        # NODATE80A01H501U -> 1980-01-01
        self.assertIsNotNone(d.data_nascita)
        self.assertEqual(d.data_nascita.year, 1980)
        self.assertEqual(d.data_nascita.month, 1)
        self.assertEqual(d.data_nascita.day, 1)

from core.models import Cliente, ProximityLog
from core.utils_kandor_chat import check_proximity

class ProximityTestCase(TestCase):
    def test_proximity_logging(self):
        # 1. Create a Dipendente
        dip = Dipendente.objects.create(
            nome='Mario', cognome='Rossi',
            codice_fiscale='RSSMRA80A01H501U',
            stato='ATTIVO',
            indirizzo_residenza='Via Fittizia 1'
        )
        Dipendente.objects.filter(pk=dip.pk).update(latitudine=45.0, longitudine=9.0)
        dip.refresh_from_db()
        
        # 2. Create a Cliente close to (45.0, 9.0)
        # 45.0, 9.0 is close to 45.0001, 9.0001 (approx 14 meters)
        cli = Cliente.objects.create(
            ragione_sociale='Cliente Prossimo',
            indirizzo_sede='Via Fittizia 2',
            ore_mensili_contratto=10
        )
        Cliente.objects.filter(pk=cli.pk).update(latitudine=45.0001, longitudine=9.0001)
        cli.refresh_from_db()
        
        # 3. Create a Cliente far from (45.0, 9.0)
        # 46.0, 10.0 is very far (approx 130 km)
        cli_far = Cliente.objects.create(
            ragione_sociale='Cliente Lontano',
            indirizzo_sede='Via Fittizia 3',
            ore_mensili_contratto=10
        )
        Cliente.objects.filter(pk=cli_far.pk).update(latitudine=46.0, longitudine=10.0)
        cli_far.refresh_from_db()
        
        # 4. Check proximity
        events = check_proximity(dip, 45.0, 9.0)
        
        # Should have 1 entry event (for Cliente Prossimo)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'entry')
        self.assertEqual(events[0]['cliente'], cli)
        
        # ProximityLog should have been created for cli
        log_cli = ProximityLog.objects.get(dipendente=dip, cliente=cli)
        self.assertTrue(log_cli.is_near)
        self.assertIsNotNone(log_cli.entered_at)
        self.assertIsNone(log_cli.exited_at)
        
        # Now move far away
        events_far = check_proximity(dip, 46.0, 10.0)
        
        # Should have 1 exit event for cli, and 1 entry event for cli_far
        self.assertEqual(len(events_far), 2)
        
        types = [e['type'] for e in events_far]
        clienti = [e['cliente'] for e in events_far]
        
        self.assertIn('exit', types)
        self.assertIn('entry', types)
        self.assertIn(cli, clienti)
        self.assertIn(cli_far, clienti)
        
        # ProximityLog for cli should now be is_near=False
        log_cli.refresh_from_db()
        self.assertFalse(log_cli.is_near)
        self.assertIsNotNone(log_cli.exited_at)

from core.models import ProgrammazioneRicorrente, Squadra, Cliente, Turno, AssegnazioneTurno
from core.services import genera_turni_automatici

class PastShiftsGenerationTestCase(TestCase):
    def test_past_shifts_generated_from_contract_start_date(self):
        today = timezone.now().date()
        past_start = today - timedelta(days=14)
        
        dip = Dipendente.objects.create(nome='Capo', cognome='Test', codice_fiscale='CAPO002')
        squadra = Squadra.objects.create(nome='Squadra Past', caposquadra=dip)
        cliente = Cliente.objects.create(ragione_sociale='Cliente Past', ore_mensili_contratto=20)
        
        # Create recurring schedule starting 14 days ago on the weekday of past_start
        prog = ProgrammazioneRicorrente.objects.create(
            cliente=cliente,
            tipo_ripetizione='SETTIMANALE',
            giorno_settimana=past_start.weekday(),
            ora_inizio=datetime.time(8, 0),
            durata=4.0,
            squadra_abituale=squadra,
            data_inizio_contratto=past_start
        )
        
        # Verify that an AssegnazioneTurno was created for past_start
        past_assign = AssegnazioneTurno.objects.filter(
            programmazione_feriale=prog,
            turno__data=past_start
        )
        self.assertTrue(past_assign.exists(), "Shift for past_start should have been generated upon saving ProgrammazioneRicorrente.")
        
        # Call genera_turni_automatici() and verify it runs smoothly without removing or missing past shifts
        count = genera_turni_automatici()
        self.assertTrue(AssegnazioneTurno.objects.filter(programmazione_feriale=prog, turno__data=past_start).exists())


from core.models import Assenza, RichiestaSostituzione
from core.utils_kandor_chat import _gestisci_assenza_con_sostituzione, handle_telegram_callback
from core.services import avvalla_assenza_da_amministrazione, rifiuta_assenza_da_amministrazione

class AvvalloAssenzaTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser('admin_avvallo', 'avvallo@kandor.it', 'pass1234')
        self.client.force_login(self.admin_user)
        self.today = timezone.now().date()
        self.dip = Dipendente.objects.create(
            nome='Mario', cognome='Rossi', codice_fiscale='MRORSS80A01H501U',
            telegram_chat_id='12345678', stato='ATTIVO', is_sostituto=False
        )
        self.sostituto = Dipendente.objects.create(
            nome='Giuseppe', cognome='Verdi', codice_fiscale='VRDGPP80A01H501Z',
            telegram_chat_id='87654321', stato='ATTIVO', is_sostituto=True
        )
        self.squadra = Squadra.objects.create(nome='Squadra Alfa', caposquadra=self.dip)
        self.cliente = Cliente.objects.create(ragione_sociale='Cliente Test', ore_mensili_contratto=100)
        self.turno = Turno.objects.create(data=self.today, squadra=self.squadra)
        self.assegnazione = AssegnazioneTurno.objects.create(
            turno=self.turno, cliente=self.cliente,
            orario_inizio_previsto=datetime.time(8, 0),
            orario_fine_previsto=datetime.time(16, 0)
        )

    def test_assenza_requires_admin_avvallo_before_replacement(self):
        # 1. Dipendente manda messaggio di Malattia via Telegram
        res = _gestisci_assenza_con_sostituzione(
            self.dip, 'MALATTIA', 'Registrata malattia', 'Invia certificato',
            data_inizio=self.today, data_fine=self.today
        )
        
        # L'assenza deve essere in stato IN_ATTESA
        assenza = Assenza.objects.get(dipendente=self.dip, tipo='MALATTIA')
        self.assertEqual(assenza.stato_approvazione, 'IN_ATTESA')
        self.assertFalse(assenza.is_processed)

        # NESSUNA richiesta di sostituzione deve essere stata creata finché non c'è l'avvallo
        req_count = RichiestaSostituzione.objects.filter(dipendente_assente=self.dip).count()
        self.assertEqual(req_count, 0)

        # 2. L'Amministrazione avvalla la richiesta (tramite servizio / callback Telegram)
        res_avvallo = avvalla_assenza_da_amministrazione(assenza.pk)
        self.assertTrue(res_avvallo['ok'])
        
        assenza.refresh_from_db()
        self.assertEqual(assenza.stato_approvazione, 'APPROVATA')
        self.assertTrue(assenza.is_processed)

        # DOPO L'AVVALLO, la procedura di sostituzione deve essere stata avviata in automatico
        req_count_after = RichiestaSostituzione.objects.filter(dipendente_assente=self.dip).count()
        self.assertEqual(req_count_after, 1)

    def test_assenza_rejected_by_admin(self):
        # Dipendente richiede Ferie
        _gestisci_assenza_con_sostituzione(
            self.dip, 'FERIE', 'Richiesta ferie', '',
            data_inizio=self.today, data_fine=self.today
        )
        assenza = Assenza.objects.get(dipendente=self.dip, tipo='FERIE')
        
        # Admin Rifiuta l'assenza
        res_rifiuto = rifiuta_assenza_da_amministrazione(assenza.pk)
        self.assertTrue(res_rifiuto['ok'])

        assenza.refresh_from_db()
        self.assertEqual(assenza.stato_approvazione, 'RIFIUTATA')
        
    def test_selezione_ordinata_sostituti(self):
        # 1. Crea assenza e avvalla per generare la RichiestaSostituzione
        _gestisci_assenza_con_sostituzione(
            self.dip, 'MALATTIA', 'Registrata malattia', '',
            data_inizio=self.today, data_fine=self.today
        )
        assenza = Assenza.objects.get(dipendente=self.dip, tipo='MALATTIA')
        avvalla_assenza_da_amministrazione(assenza.pk)

        richiesta = RichiestaSostituzione.objects.get(dipendente_assente=self.dip)

        # 2. Test GET API sostituti disponibili
        response_get = self.client.get(f'/api/sostituti-disponibili/{richiesta.id}/')
        self.assertEqual(response_get.status_code, 200)
        data_get = response_get.json()
        self.assertTrue(data_get['ok'])
        self.assertIn('sostituti', data_get)

        # 3. Test POST API invia notifiche in ordine scelto
        payload = {
            'richiesta_id': richiesta.id,
            'sostituti_ids': [self.sostituto.id]
        }
        response_post = self.client.post(
            '/api/invia-notifiche-sostituti/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response_post.status_code, 200)
        data_post = response_post.json()
        self.assertTrue(data_post['ok'])
        
        richiesta.refresh_from_db()
        self.assertEqual(richiesta.sostituti_candidati, [self.sostituto.id])
        self.assertEqual(richiesta.stato, 'INVIATA')
        self.assertEqual(richiesta.sostituto, self.sostituto)


from core.models import ModificaCedolino

class ModificaCedolinoTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser('admin_cedolino', 'cedolino@kandor.it', 'pass1234')
        self.client.force_login(self.admin_user)
        self.today = timezone.now().date()
        self.data_inizio = self.today.replace(day=1)
        self.data_fine = self.today
        self.dip = Dipendente.objects.create(
            nome='Mario', cognome='Rossi', codice_fiscale='MRORSS80A01H501U',
            stato='ATTIVO'
        )

    def test_salva_modifica_cedolino_ajax(self):
        # 1. Salva una nuova rettifica via AJAX
        payload = {
            'dipendente_id': self.dip.id,
            'data_inizio': self.data_inizio.isoformat(),
            'data_fine': self.data_fine.isoformat(),
            'giorni_lavorati_override': 18,
            'ore_lavorate_override': 144.0,
            'ore_validate_override': 144.0,
            'giorni_ferie_override': 2,
            'giorni_permesso_override': 0,
            'giorni_malattia_override': 0,
            'note': 'Straordinari cantiere approvati manuale',
            'reset': False
        }
        res = self.client.post(
            '/report-paghe/salva-modifica/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])

        modifica = ModificaCedolino.objects.get(
            dipendente=self.dip, data_inizio=self.data_inizio, data_fine=self.data_fine
        )
        self.assertEqual(modifica.giorni_lavorati_override, 18)
        self.assertEqual(modifica.ore_lavorate_override, 144.0)
        self.assertEqual(modifica.note, 'Straordinari cantiere approvati manuale')

        # 2. Verifica che report_paghe_view applichi i dati rettificati
        url = f'/report-paghe/?data_inizio={self.data_inizio.isoformat()}&data_fine={self.data_fine.isoformat()}&dipendente_id={self.dip.id}'
        res_view = self.client.get(url)
        self.assertEqual(res_view.status_code, 200)
        report_list = res_view.context['report_list']
        self.assertEqual(len(report_list), 1)
        item = report_list[0]
        self.assertTrue(item['is_rettificato'])
        self.assertEqual(item['giorni_lavorati'], 18)
        self.assertEqual(item['ore_lavorate'], 144.0)

        # 3. Ripristina i valori calcolati via AJAX (reset=True)
        reset_payload = {
            'dipendente_id': self.dip.id,
            'data_inizio': self.data_inizio.isoformat(),
            'data_fine': self.data_fine.isoformat(),
            'reset': True
        }
        res_reset = self.client.post(
            '/report-paghe/salva-modifica/',
            data=json.dumps(reset_payload),
            content_type='application/json'
        )
        self.assertEqual(res_reset.status_code, 200)
        self.assertFalse(
            ModificaCedolino.objects.filter(
                dipendente=self.dip, data_inizio=self.data_inizio, data_fine=self.data_fine
            ).exists()
        )







from django.core.exceptions import ValidationError

class DipendentePartTimeTestCase(TestCase):
    def test_part_time_validation_requires_tipo_part_time(self):
        dip = Dipendente(
            nome='PartTime', cognome='Test', codice_fiscale='PRTTST80A01H501Z',
            is_part_time=True, tipo_part_time=None
        )
        with self.assertRaises(ValidationError) as ctx:
            dip.clean()
        self.assertIn('tipo_part_time', ctx.exception.message_dict)

    def test_part_time_valid_choices(self):
        for idx, choice in enumerate(['M', 'V', 'O']):
            dip = Dipendente(
                nome='PartTime', cognome=f'Test{idx}', codice_fiscale=f'PRTTST80A01H50{idx}Z',
                is_part_time=True, tipo_part_time=choice
            )
            dip.clean()  # Should not raise
            dip.save()
            self.assertEqual(dip.tipo_part_time, choice)

    def test_admin_part_time_display(self):
        from core.admin import DipendenteAdmin
        from django.contrib.admin.sites import AdminSite
        admin_obj = DipendenteAdmin(Dipendente, AdminSite())

        dip_full = Dipendente.objects.create(
            nome='Full', cognome='Time', codice_fiscale='FLLTIM80A01H501Z',
            is_part_time=False
        )
        self.assertEqual(admin_obj.part_time_display(dip_full), "Full-Time")

        dip_part = Dipendente.objects.create(
            nome='Part', cognome='Time', codice_fiscale='PRTTIM80A01H501Z',
            is_part_time=True, tipo_part_time='M'
        )
        self.assertEqual(admin_obj.part_time_display(dip_part), "Part-Time (M - Misto)")


from core.models import TimeTracking
from decimal import Decimal


class PreservazioneTurniPassatiTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser('admin_preserv', 'preserv@kandor.it', 'pass1234')
        self.client.force_login(self.admin_user)
        self.today = timezone.now().date()
        self.past_date = self.today - timedelta(days=5)
        self.future_date = self.today + timedelta(days=5)

        self.capo = Dipendente.objects.create(
            nome='Marco', cognome='Capo', codice_fiscale='CPOMRC80A01H501A', stato='ATTIVO'
        )
        self.comp1 = Dipendente.objects.create(
            nome='Luca', cognome='Bianchi', codice_fiscale='BNCLCU80A01H501B', stato='ATTIVO'
        )
        self.comp2 = Dipendente.objects.create(
            nome='Paolo', cognome='Neri', codice_fiscale='NRIPLA80A01H501C', stato='ATTIVO'
        )

        self.squadra = Squadra.objects.create(nome='Squadra Storica', caposquadra=self.capo)
        self.squadra.componenti.add(self.comp1)

        self.cliente = Cliente.objects.create(ragione_sociale='Cliente Storico', ore_mensili_contratto=40)

        # Turno passato con ore lavorate
        self.turno_past = Turno.objects.create(data=self.past_date, squadra=self.squadra)
        self.assign_past = AssegnazioneTurno.objects.create(
            turno=self.turno_past,
            cliente=self.cliente,
            orario_inizio_previsto=datetime.time(8, 0),
            orario_fine_previsto=datetime.time(12, 0),
            ore_previste_contratto=4.0,
        )
        self.tt_past_capo = TimeTracking.objects.create(
            dipendente=self.capo,
            assegnazione=self.assign_past,
            ore_dichiarate=Decimal('4.00'),
            is_validated=True,
            source='ADMIN',
        )
        self.tt_past_comp1 = TimeTracking.objects.create(
            dipendente=self.comp1,
            assegnazione=self.assign_past,
            ore_dichiarate=Decimal('4.00'),
            is_validated=True,
            source='ADMIN',
        )

        # Turno futuro
        self.turno_future = Turno.objects.create(data=self.future_date, squadra=self.squadra)
        self.assign_future = AssegnazioneTurno.objects.create(
            turno=self.turno_future,
            cliente=self.cliente,
            orario_inizio_previsto=datetime.time(8, 0),
            orario_fine_previsto=datetime.time(12, 0),
            ore_previste_contratto=4.0,
        )

    def test_1_eliminazione_squadra_preserva_turni_passati_cancella_futuri(self):
        past_turno_id = self.turno_past.id
        future_turno_id = self.turno_future.id

        # Elimina la squadra
        self.squadra.delete()

        # Il turno futuro deve essere stato cancellato
        self.assertFalse(Turno.objects.filter(id=future_turno_id).exists())
        self.assertFalse(AssegnazioneTurno.objects.filter(id=self.assign_future.id).exists())

        # Il turno passato, l'assegnazione e le ore lavorate devono essere intatti!
        self.assertTrue(Turno.objects.filter(id=past_turno_id).exists())
        turno_past_db = Turno.objects.get(id=past_turno_id)
        self.assertIsNone(turno_past_db.squadra)
        self.assertEqual(turno_past_db.nome_squadra, 'Squadra Storica')
        self.assertEqual(TimeTracking.objects.filter(assegnazione=self.assign_past).count(), 2)

    def test_2_modifica_squadra_preserva_turni_passati(self):
        # Crea anche un turno nel mese precedente (cedolino chiuso)
        prev_month_date = self.today.replace(day=1) - timedelta(days=5)
        turno_prev_month = Turno.objects.create(data=prev_month_date, squadra=self.squadra)
        assign_prev_month = AssegnazioneTurno.objects.create(
            turno=turno_prev_month,
            cliente=self.cliente,
            orario_inizio_previsto=datetime.time(8, 0),
            orario_fine_previsto=datetime.time(12, 0),
            ore_previste_contratto=4.0,
        )

        # Rimuovi comp1 e aggiungi comp2 alla squadra
        self.squadra.componenti.remove(self.comp1)
        self.squadra.componenti.add(self.comp2)

        # Nel mese precedente (chiuso): comp2 è escluso
        assign_prev_month.refresh_from_db()
        esclusi_prev_month = set(assign_prev_month.dipendenti_esclusi.values_list('pk', flat=True))
        self.assertIn(self.comp2.pk, esclusi_prev_month)

        # Nel turno passato: comp1 NON è escluso e conserva le sue 4 ore;
        # se past_date è nel mese corrente, comp2 riceve la retroattività dal 1° del mese
        self.assign_past.refresh_from_db()
        esclusi_past = set(self.assign_past.dipendenti_esclusi.values_list('pk', flat=True))
        self.assertNotIn(self.comp1.pk, esclusi_past)
        self.assertTrue(
            TimeTracking.objects.filter(assegnazione=self.assign_past, dipendente=self.comp1, ore_dichiarate=Decimal('4.00')).exists()
        )
        if self.past_date >= self.today.replace(day=1):
            self.assertNotIn(self.comp2.pk, esclusi_past)
            self.assertTrue(
                TimeTracking.objects.filter(assegnazione=self.assign_past, dipendente=self.comp2, ore_dichiarate=Decimal('4.00')).exists()
            )
        else:
            self.assertIn(self.comp2.pk, esclusi_past)

    def test_3_licenziamento_dipendente_cancella_solo_futuri_preserva_cedolini_passati(self):
        # Aggiungi anche un TimeTracking futuro pre-compilato per verificare che venga rimosso
        TimeTracking.objects.create(
            dipendente=self.comp1,
            assegnazione=self.assign_future,
            ore_dichiarate=Decimal('4.00'),
            is_validated=False,
        )

        # Licenzia comp1 in data odierna
        self.comp1.stato = 'INATTIVO'
        self.comp1.data_licenziamento = self.today
        self.comp1.save()

        # Nel turno futuro comp1 è stato escluso e il TimeTracking futuro è stato cancellato
        self.assertFalse(TimeTracking.objects.filter(assegnazione=self.assign_future, dipendente=self.comp1).exists())
        self.assertIn(self.comp1.pk, set(self.assign_future.dipendenti_esclusi.values_list('pk', flat=True)))

        # Nel turno passato comp1 mantiene le sue ore e NON è escluso
        self.assertTrue(
            TimeTracking.objects.filter(assegnazione=self.assign_past, dipendente=self.comp1, ore_dichiarate=Decimal('4.00')).exists()
        )
        self.assertNotIn(self.comp1.pk, set(self.assign_past.dipendenti_esclusi.values_list('pk', flat=True)))

        # Verifica che il dipendente licenziato compaia regolarmente nel report cedolini paghe del periodo
        data_inizio = (self.past_date - timedelta(days=2)).isoformat()
        data_fine = self.today.isoformat()
        res = self.client.get(f'/report-paghe/?data_inizio={data_inizio}&data_fine={data_fine}')
        self.assertEqual(res.status_code, 200)
        report_list = res.context['report_list']
        comp1_row = next((r for r in report_list if r['dip_id'] == self.comp1.pk), None)
        self.assertIsNotNone(comp1_row, "Il dipendente licenziato con ore nel periodo deve comparire nel report cedolini paghe!")
        self.assertEqual(comp1_row['ore_lavorate'], 4.0)
        self.assertEqual(comp1_row['ore_validate'], 4.0)
        self.assertEqual(comp1_row['giorni_lavorati'], 1)


class CorsiFormazioneTestCase(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.today = timezone.now().date()
        self.dip = Dipendente.objects.create(
            nome="Mario",
            cognome="Rossi",
            codice_fiscale="RSSMRA80A01H501U",
            indirizzo_residenza="Via Roma 1",
            stato="ATTIVO",
        )

    def test_1_default_10_corsi_presenti_e_aggiunta_nuovo_corso(self):
        from core.models import CorsoFormazione, CorsoDipendente, ensure_corsi_per_dipendente
        ensure_corsi_per_dipendente(self.dip)

        expected_names = [
            "Corso sicurezza generale",
            "Corso Specifico Basso Rischio",
            "Corso Movimentazione manuale carichi",
            "Corso DPI 3 lavori in quota",
            "Corso RLS",
            "Corso preposto",
            "Corso primo soccorso",
            "Corso piattaforme mobili con o senza stabilizzatori",
            "Corso HACCP",
            "Corso antincendio livello 2",
        ]
        corsi_dip = list(CorsoDipendente.objects.filter(dipendente=self.dip).select_related('corso'))
        nomi_dip = [c.corso.nome for c in corsi_dip]
        for expected in expected_names:
            self.assertIn(expected, nomi_dip)

        # Aggiunta di un nuovo corso in futuro
        nuovo = CorsoFormazione.objects.create(nome="Corso Spazi Confinati", ordine=11, attivo=True)
        ensure_corsi_per_dipendente(self.dip)
        self.assertTrue(CorsoDipendente.objects.filter(dipendente=self.dip, corso=nuovo).exists())

    def test_2_alert_dashboard_20_giorni_prima_scadenza(self):
        from core.models import CorsoDipendente, ensure_corsi_per_dipendente
        from core.templatetags.dashboard_extras import expiring_training_courses_widget

        ensure_corsi_per_dipendente(self.dip)
        c_haccp = CorsoDipendente.objects.get(dipendente=self.dip, corso__nome="Corso HACCP")
        c_rls = CorsoDipendente.objects.get(dipendente=self.dip, corso__nome="Corso RLS")

        # 1) Corso eseguito 2 anni fa + 25 gg -> scadenza automatica tra 25 giorni -> NON deve comparire nell'alert 20 gg
        target_25 = self.today + timedelta(days=25)
        c_haccp.stato = 'FATTO'
        c_haccp.data_esecuzione = target_25.replace(year=target_25.year - 2)
        c_haccp.save()
        self.assertEqual(c_haccp.data_scadenza, target_25)

        ctx = expiring_training_courses_widget()
        self.assertFalse(ctx['has_urgent'])
        self.assertEqual(len(ctx['training_courses']), 0)

        # 2) Corso eseguito 2 anni fa + 15 gg -> scadenza automatica tra 15 giorni (entro 20 gg) -> DEVE comparire nell'alert
        target_15 = self.today + timedelta(days=15)
        c_haccp.data_esecuzione = target_15.replace(year=target_15.year - 2)
        c_haccp.save()
        self.assertEqual(c_haccp.data_scadenza, target_15)

        # 3) Corso "Deve essere fatto" gia' scaduto ieri -> DEVE comparire come SCADUTO
        c_rls.stato = 'DA_FARE'
        c_rls.data_scadenza = self.today - timedelta(days=1)
        c_rls.save()

        ctx = expiring_training_courses_widget()
        self.assertTrue(ctx['has_urgent'])
        self.assertEqual(len(ctx['training_courses']), 2)
        # Il primo ordinato per data_scadenza e' quello scaduto ieri
        self.assertTrue(ctx['training_courses'][0]['is_expired'])
        self.assertEqual(ctx['training_courses'][0]['corso'].nome, "Corso RLS")
        self.assertFalse(ctx['training_courses'][1]['is_expired'])
        self.assertEqual(ctx['training_courses'][1]['corso'].nome, "Corso HACCP")

    def test_3_durate_corsi_e_calcolo_automatico_scadenza(self):
        from core.models import CorsoFormazione, CorsoDipendente, ensure_corsi_per_dipendente
        ensure_corsi_per_dipendente(self.dip)

        expected_durations = {
            "Corso sicurezza generale": 5,
            "Corso Specifico Basso Rischio": 5,
            "Corso Movimentazione manuale carichi": 5,
            "Corso DPI 3 lavori in quota": 5,
            "Corso RLS": 3,
            "Corso preposto": 2,
            "Corso primo soccorso": 3,
            "Corso piattaforme mobili con o senza stabilizzatori": 5,
            "Corso HACCP": 2,
            "Corso antincendio livello 2": 5,
        }
        for nome_corso, durata_attesa in expected_durations.items():
            corso = CorsoFormazione.objects.get(nome=nome_corso)
            self.assertEqual(corso.durata_anni, durata_attesa, f"Durata errata per {nome_corso}")

        # Verifica calcolo automatico scadenza:
        # 1) Corso sicurezza generale (durata 5 anni)
        cd_sic = CorsoDipendente.objects.get(dipendente=self.dip, corso__nome="Corso sicurezza generale")
        cd_sic.data_esecuzione = datetime.date(2024, 3, 15)
        cd_sic.save()
        self.assertEqual(cd_sic.stato, 'FATTO')
        self.assertEqual(cd_sic.data_scadenza, datetime.date(2029, 3, 15))

        # 2) Corso RLS (durata 3 anni)
        cd_rls = CorsoDipendente.objects.get(dipendente=self.dip, corso__nome="Corso RLS")
        cd_rls.data_esecuzione = datetime.date(2024, 5, 10)
        cd_rls.save()
        self.assertEqual(cd_rls.stato, 'FATTO')
        self.assertEqual(cd_rls.data_scadenza, datetime.date(2027, 5, 10))

        # 3) Corso preposto (durata 2 anni)
        cd_prep = CorsoDipendente.objects.get(dipendente=self.dip, corso__nome="Corso preposto")
        cd_prep.data_esecuzione = datetime.date(2025, 1, 20)
        cd_prep.save()
        self.assertEqual(cd_prep.stato, 'FATTO')
        self.assertEqual(cd_prep.data_scadenza, datetime.date(2027, 1, 20))

        # 4) Nuovo corso aggiunto con durata personalizzata (es. 4 anni) e anno bisestile 29/02/2024 -> 29/02/2028
        nuovo = CorsoFormazione.objects.create(nome="Corso Carrelli Elevatori", durata_anni=4, ordine=12, attivo=True)
        cd_nuovo = CorsoDipendente.objects.create(
            dipendente=self.dip,
            corso=nuovo,
            data_esecuzione=datetime.date(2024, 2, 29),
        )
        self.assertEqual(cd_nuovo.stato, 'FATTO')
        self.assertEqual(cd_nuovo.data_scadenza, datetime.date(2028, 2, 29))

    def test_4_mezzo_scadenza_permesso_citta_alta_bergamo(self):
        from core.models import Mezzo
        from core.templatetags.dashboard_extras import expiring_vehicles_widget

        mezzo = Mezzo.objects.create(
            modello="Fiat Ducato",
            targa="BG123CA",
            stato="DISPONIBILE",
            scadenza_permesso_citta_alta=self.today + timedelta(days=10),
        )
        ctx = expiring_vehicles_widget()
        self.assertEqual(len(ctx['vehicles']), 1)
        alerts = ctx['vehicles'][0]['alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['type'], 'Permesso Città Alta (BG)')
        self.assertEqual(alerts[0]['date'], mezzo.scadenza_permesso_citta_alta)

    def test_5_telegram_allegati_cedolini_e_foto(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.models import MessaggioChat
        from core.utils_kandor_chat import prepare_uploaded_attachments, send_and_record_telegram_to_employee

        self.dip.telegram_chat_id = "123456789"
        self.dip.save()

        pdf_file = SimpleUploadedFile(
            "cedolino_ottobre_2026.pdf",
            b"%PDF-1.4 fake pdf content",
            content_type="application/pdf",
        )
        img_file = SimpleUploadedFile(
            "foto_cantiere.jpg",
            b"\xff\xd8\xff\xe0fake jpg content",
            content_type="image/jpeg",
        )

        with patch("core.utils_kandor_chat.send_telegram_file", return_value=True) as mock_send_file, \
             patch("core.utils_kandor_chat._save_uploaded_attachment_storage", side_effect=[
                 "/media/chat_allegati/cedolino_ottobre_2026.pdf",
                 "/media/chat_allegati/foto_cantiere.jpg",
             ]):
            attachments = prepare_uploaded_attachments([pdf_file, img_file])
            ok = send_and_record_telegram_to_employee(
                self.dip,
                text="Ecco il cedolino paga e la foto",
                attachments=attachments,
            )
            self.assertTrue(ok)
            self.assertEqual(mock_send_file.call_count, 2)

        msgs = list(MessaggioChat.objects.filter(dipendente=self.dip, direzione='OUT').order_by('id'))
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].allegato_nome, "cedolino_ottobre_2026.pdf")
        self.assertEqual(msgs[0].allegato_url, "/media/chat_allegati/cedolino_ottobre_2026.pdf")
        self.assertIn("Ecco il cedolino paga e la foto", msgs[0].testo)
        self.assertEqual(msgs[1].allegato_nome, "foto_cantiere.jpg")
        self.assertEqual(msgs[1].foto_url, "/media/chat_allegati/foto_cantiere.jpg")


class AIEngineAndHubTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Mezzo
        self.today = timezone.now().date()
        self.admin_user = User.objects.create_superuser('admin_ia', 'ia@kandor.it', 'pass1234')
        self.client.force_login(self.admin_user)

        self.dip_capo = Dipendente.objects.create(
            nome='Marco', cognome='Bianchi', codice_fiscale='BNCMRC80A01H501A',
            stato='ATTIVO', is_sostituto=False
        )
        self.jolly_esperto = Dipendente.objects.create(
            nome='Luigi', cognome='Esperto', codice_fiscale='SPRLGU80A01H501B',
            stato='ATTIVO', is_sostituto=True,
            data_ultima_visita_medica=self.today + timedelta(days=180),
        )
        self.jolly_nuovo = Dipendente.objects.create(
            nome='Andrea', cognome='Nuovo', codice_fiscale='NVONDR80A01H501C',
            stato='ATTIVO', is_sostituto=True,
            data_ultima_visita_medica=self.today + timedelta(days=180),
        )

        self.squadra = Squadra.objects.create(nome='Squadra Bergamo', caposquadra=self.dip_capo)
        self.mezzo = Mezzo.objects.create(
            modello='Furgone ZTL', targa='BG999CA', stato='DISPONIBILE',
            scadenza_permesso_citta_alta=self.today - timedelta(days=5),  # Scaduto!
        )
        self.cliente = Cliente.objects.create(
            ragione_sociale='Condominio Città Alta',
            indirizzo_sede='Via Gombito 1, Città Alta Bergamo',
            ore_mensili_contratto=20,
            importo_mensile_contratto=Decimal('500.00'),
            note_mansioni='Pulizia vetri con lavori in quota',
        )
        self.turno = Turno.objects.create(data=self.today, squadra=self.squadra, mezzo=self.mezzo)
        self.assegnazione = AssegnazioneTurno.objects.create(
            turno=self.turno,
            cliente=self.cliente,
            orario_inizio_previsto=datetime.time(8, 0),
            orario_fine_previsto=datetime.time(12, 0),
        )

    def test_1_audit_ore_e_auto_validazione_1_click(self):
        from core.ai_engine import analizza_anomalie_ore
        # 1 registrazione regolare (4h su 4h previste) e 1 anomala (9h su 4h previste)
        tt_ok = TimeTracking.objects.create(
            dipendente=self.dip_capo,
            assegnazione=self.assegnazione,
            ore_dichiarate=Decimal('4.00'),
            is_validated=False,
        )
        tt_anom = TimeTracking.objects.create(
            dipendente=self.jolly_nuovo,
            assegnazione=self.assegnazione,
            ore_dichiarate=Decimal('9.50'),
            is_validated=False,
        )
        audit = analizza_anomalie_ore(self.today, self.today)
        self.assertIn(tt_ok.id, audit['auto_validabili_ids'])
        self.assertNotIn(tt_anom.id, audit['auto_validabili_ids'])
        self.assertEqual(audit['riepilogo']['anomalie_count'], 1)

        # Chiama l'endpoint 1-click auto-validazione
        res = self.client.post(
            '/api/ia/auto-valida-ore/',
            data=json.dumps({'data_inizio': self.today.isoformat(), 'data_fine': self.today.isoformat()}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        tt_ok.refresh_from_db()
        tt_anom.refresh_from_db()
        self.assertTrue(tt_ok.is_validated)
        self.assertFalse(tt_anom.is_validated)

    def test_2_nlp_assistente_triage_e_documenti(self):
        from core.ai_engine import classifica_segnalazione, interpreta_messaggio_libero, analizza_documento_o_certificato
        # Triage segnalazione critica
        triage = classifica_segnalazione("Scintille elettriche e fumo dalla lavasciuga")
        self.assertEqual(triage['urgenza'], 'CRITICA')
        self.assertEqual(triage['categoria'], 'SICUREZZA')

        # NLP messaggio libero ore
        parsed_ore = interpreta_messaggio_libero(self.dip_capo, "Oggi ho fatto 4 ore da Condominio Città Alta")
        self.assertEqual(parsed_ore['intent'], 'REGISTRA_ORE')
        self.assertEqual(parsed_ore['ore'], 4.0)
        self.assertEqual(parsed_ore['assegnazione_id'], self.assegnazione.id)

        # NLP messaggio libero assenza
        parsed_ass = interpreta_messaggio_libero(self.dip_capo, "Domani sono in malattia con febbre")
        self.assertEqual(parsed_ass['intent'], 'ASSENZA')
        self.assertEqual(parsed_ass['tipo_assenza'], 'MALATTIA')

        # Parser documento/attestato corso
        doc_res = analizza_documento_o_certificato("Attestato Corso DPI 3 lavori in quota eseguito il 10/10/2026")
        self.assertEqual(doc_res['tipo_documento'], 'ATTESTATO_CORSO')
        self.assertEqual(doc_res['corso_nome'], 'Corso DPI 3 lavori in quota')

    def test_3_smart_sostituzioni_ranking_predittivo(self):
        from core.services import trova_sostituti
        from core.models import ensure_corsi_per_dipendente, CorsoDipendente
        # Diamo a jolly_esperto il corso richiesto + 3 presenze storiche sul cliente
        ensure_corsi_per_dipendente(self.jolly_esperto)
        ensure_corsi_per_dipendente(self.jolly_nuovo)
        cd = CorsoDipendente.objects.get(dipendente=self.jolly_esperto, corso__nome="Corso DPI 3 lavori in quota")
        cd.data_esecuzione = self.today - timedelta(days=60)
        cd.save()

        for i in range(1, 4):
            t_old = Turno.objects.create(data=self.today - timedelta(days=i), squadra=self.squadra)
            a_old = AssegnazioneTurno.objects.create(
                turno=t_old, cliente=self.cliente,
                orario_inizio_previsto=datetime.time(8, 0),
                orario_fine_previsto=datetime.time(12, 0),
            )
            TimeTracking.objects.create(
                dipendente=self.jolly_esperto,
                assegnazione=a_old,
                ore_dichiarate=Decimal('4.00'),
                is_validated=True,
            )

        risultati = trova_sostituti(
            cliente=self.cliente,
            data=self.today + timedelta(days=1),
            ora_inizio=datetime.time(8, 0),
            ora_fine=datetime.time(12, 0),
        )
        self.assertTrue(len(risultati) >= 2)
        # jolly_esperto deve essere classificato prima di jolly_nuovo grazie allo Smart Score IA superiore
        self.assertEqual(risultati[0]['dipendente'].id, self.jolly_esperto.id)
        self.assertGreater(risultati[0]['ai_score'], risultati[1]['ai_score'])

    def test_4_compliance_guardian_ztl_citta_alta_e_corsi(self):
        from core.ai_engine import verifica_conformita_turni
        comp = verifica_conformita_turni(data_inizio=self.today, giorni=3)
        self.assertGreaterEqual(comp['totale_alert'], 1)
        categorie = [a['categoria'] for a in comp['alerts']]
        self.assertIn('ZTL_CITTA_ALTA', categorie)

    def test_5_marginalita_burn_rate_e_lavori_extra_e_hub_view(self):
        from core.ai_engine import analizza_marginalita_e_budget_clienti
        TimeTracking.objects.create(
            dipendente=self.dip_capo,
            assegnazione=self.assegnazione,
            ore_dichiarate=Decimal('6.00'),
            note='Effettuato intervento extra per allagamento cantina richiesto dal cliente',
            is_validated=True,
        )
        marg = analizza_marginalita_e_budget_clienti(anno=self.today.year, mese=self.today.month)
        self.assertEqual(len(marg['lavori_extra']), 1)
        self.assertEqual(marg['lavori_extra'][0]['cliente_nome'], 'Condominio Città Alta')

        # Verifica che la dashboard /ia-hub/ risponda 200 OK e includa l'intestazione con logo e link Home
        resp = self.client.get('/ia-hub/')
        self.assertEqual(resp.status_code, 200)
        html_content = resp.content.decode('utf-8')
        self.assertIn('core/img/logo.png', html_content)
        self.assertIn('KANDOR ERP', html_content)
        self.assertIn('href="/admin/"', html_content)

    def test_6_inserimento_ore_amministrazione_da_turno_calendario(self):
        # Nessun TimeTracking ancora inviato dal lavoratore per self.assegnazione
        self.assertEqual(TimeTracking.objects.filter(assegnazione=self.assegnazione).count(), 0)

        # L'amministrazione inserisce e valida le ore (es. 4.5h) dalla modale del turno nel calendario
        resp = self.client.post(
            f'/api/validate-ore/{self.assegnazione.id}/',
            data=json.dumps({'ore': 4.5, 'validate': True, 'dipendenti_esclusi': []}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['validated'])
        self.assertEqual(data['count'], 1)

        tt = TimeTracking.objects.get(assegnazione=self.assegnazione, dipendente=self.dip_capo)
        self.assertEqual(tt.ore_dichiarate, Decimal('4.5'))
        self.assertTrue(tt.is_validated)
        self.assertEqual(tt.source, 'ADMIN')

    def test_7_deselezione_dipendente_e_selezione_sostituto_diretta_da_turno(self):
        from core.models import RichiestaSostituzione
        from core.views_webapp import _get_assegnazioni_dipendente

        # 1. Verifica che get_assegnazione_componenti_json restituisca sostituti_disponibili
        resp_comp = self.client.get(f'/api/assegnazione-componenti/{self.assegnazione.id}/')
        self.assertEqual(resp_comp.status_code, 200)
        comp_data = resp_comp.json()
        self.assertIn('sostituti_disponibili', comp_data)
        sost_ids = [s['id'] for s in comp_data['sostituti_disponibili']]
        self.assertIn(self.jolly_nuovo.id, sost_ids)

        # 2. Deseleziona self.dip_capo e seleziona self.jolly_nuovo come sostituto direttamente dalla scheda del turno
        resp_sost = self.client.post(
            f'/api/assegna-sostituto-turno/{self.assegnazione.id}/',
            data=json.dumps({
                'dipendente_escluso_id': self.dip_capo.id,
                'sostituto_id': self.jolly_nuovo.id,
                'dipendenti_esclusi': [self.dip_capo.id],
                'sostituzioni_esclusi': {str(self.dip_capo.id): self.jolly_nuovo.id},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp_sost.status_code, 200)
        self.assertEqual(resp_sost.json()['status'], 'ok')

        # Verifica che dip_capo sia tra i dipendenti_esclusi e che la RichiestaSostituzione sia COMPLETATA senza validazione assenza
        self.assertIn(self.dip_capo.id, list(self.assegnazione.dipendenti_esclusi.values_list('id', flat=True)))
        req = RichiestaSostituzione.objects.get(
            assegnazione_originale=self.assegnazione,
            dipendente_assente=self.dip_capo,
        )
        self.assertEqual(req.stato, 'COMPLETATA')
        self.assertEqual(req.sostituto, self.jolly_nuovo)

        # Verifica che il sostituto veda il turno nella sua web app mobile
        assigns_sost = _get_assegnazioni_dipendente(self.jolly_nuovo, self.today)
        self.assertTrue(any(a['id'] == self.assegnazione.id and a['is_sostituzione'] for a in assigns_sost))

        # 3. Inserimento e validazione ore del turno: le ore vanno al sostituto e NON al dipendente escluso
        resp_ore = self.client.post(
            f'/api/validate-ore/{self.assegnazione.id}/',
            data=json.dumps({
                'ore': 4.0,
                'validate': True,
                'dipendenti_esclusi': [self.dip_capo.id],
                'sostituzioni_esclusi': {str(self.dip_capo.id): self.jolly_nuovo.id},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp_ore.status_code, 200)
        self.assertFalse(TimeTracking.objects.filter(assegnazione=self.assegnazione, dipendente=self.dip_capo).exists())
        tt_sost = TimeTracking.objects.get(assegnazione=self.assegnazione, dipendente=self.jolly_nuovo)
        self.assertEqual(tt_sost.ore_dichiarate, Decimal('4.0'))
        self.assertTrue(tt_sost.is_validated)

        # 4. Ri-selezionando il dipendente titolare nella scheda del turno, la sostituzione viene annullata e il TimeTracking del sostituto rimosso
        resp_riattiva = self.client.post(
            f'/api/assegna-sostituto-turno/{self.assegnazione.id}/',
            data=json.dumps({
                'dipendente_escluso_id': self.dip_capo.id,
                'sostituto_id': None,
                'riattiva_dipendente': True,
                'dipendenti_esclusi': [],
                'sostituzioni_esclusi': {},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp_riattiva.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.stato, 'ANNULLATA')
        self.assertFalse(TimeTracking.objects.filter(assegnazione=self.assegnazione, dipendente=self.jolly_nuovo).exists())


class SecurityHardeningTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser('admin', 'admin@kandor.it', 'CustomSecurePass!99')

    def test_1_debug_db_blocked_for_anonymous_and_does_not_reset_password(self):
        for debug_url in ['/debug-db/', '/ping-db/', '/test-admin-debug/', '/test-admin-debug/?step=10']:
            resp = self.client.get(debug_url)
            self.assertEqual(resp.status_code, 403, f"Endpoint {debug_url} deve essere 403 per utenti non autenticati")
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.check_password('CustomSecurePass!99'))
        self.assertFalse(self.admin_user.check_password('Kandor2024!'))

        # Anche quando chiamato da superuser, NON deve resettare la password né esporre username
        self.client.force_login(self.admin_user)
        resp_su = self.client.get('/debug-db/')
        self.assertEqual(resp_su.status_code, 200)
        data = resp_su.json()
        self.assertEqual(data.get('connection'), 'OK')
        self.assertNotIn('usernames', data)
        self.assertNotIn('admin_user_action', data)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.check_password('CustomSecurePass!99'))

    def test_2_admin_views_and_apis_require_authentication(self):
        # Utente anonimo bloccato su API di modifica (403)
        for api_url in [
            '/api/add-turno/',
            '/api/invia-notifiche-sostituti/',
            '/api/conferma-sostituto-ufficio/',
            '/report-paghe/salva-modifica/',
        ]:
            resp = self.client.post(api_url, data=json.dumps({}), content_type='application/json')
            self.assertEqual(resp.status_code, 403, f"API {api_url} dovrebbe restituire 403 agli anonimi")

        # Utente anonimo rediretto al login su viste riservate (302)
        for view_url in [
            '/report-paghe/',
            '/report-paghe/pdf/',
            '/report-paghe/csv/',
            '/verifica-ore/',
            '/analisi-contratti/',
            '/reconciliation/',
        ]:
            resp = self.client.get(view_url)
            self.assertEqual(resp.status_code, 302, f"Vista {view_url} dovrebbe redirigere al login")
            self.assertIn('/admin/login/', resp['Location'])

    def test_3_local_dev_backend_disabled_in_vps_production(self):
        import os
        from unittest.mock import patch
        from django.contrib.auth import authenticate

        with patch.dict(os.environ, {'VPS_PROD': '1', 'LOCAL_DEV': '0'}, clear=False):
            user_fallback = authenticate(username='admin', password='Kandor2024!')
            self.assertIsNone(user_fallback, "Le password di fallback dev devono essere disattivate su VPS_PROD=1")
            user_real = authenticate(username='admin', password='CustomSecurePass!99')
            self.assertIsNotNone(user_real)


class PagheRefactoringAndDedupTestCase(TestCase):
    """
    Test del Miglioramento 2:
    - Single Source of Truth in `core.paghe_service` per Report Paghe (Web, PDF, CSV)
    - Fix `KeyError: 'ore_per_giorno'` in `export_paghe_csv`
    - Fix conteggio L.104 e INFORTUNIO in `pdf_report_paghe` / `calcola_dataset_paghe`
    - Allineamento ore lavorate (`ore_dichiarate` + `check_in`/`check_out`) in `analisi_contratti_view`,
      `pdf_contratti_sotto_soglia`, `verifica_ore_view`, `pdf_verifica_ore` e `reconciliation_view`
    """
    def setUp(self):
        from django.contrib.auth.models import User
        from decimal import Decimal
        from core.models import Squadra, Turno, AssegnazioneTurno, TimeTracking, Assenza

        self.admin_user = User.objects.create_superuser(
            username='admin_paghe',
            email='admin@kandor.it',
            password='SecurePassword123!',
        )
        self.client.force_login(self.admin_user)

        self.today = datetime.date(2026, 5, 15)
        self.inizio_mese = datetime.date(2026, 5, 1)
        self.fine_mese = datetime.date(2026, 5, 31)

        self.dip = Dipendente.objects.create(
            nome="Claudio",
            cognome="Ratti",
            codice_fiscale="RTTCLD80A01B157X",
            indirizzo_residenza="Via Bergamo 10",
            stato="ATTIVO",
        )
        self.squadra = Squadra.objects.create(nome="Squadra Alfa", caposquadra=self.dip)
        self.cliente = Cliente.objects.create(
            ragione_sociale="Condominio Verdi",
            partita_iva="01234567890",
            indirizzo_sede="Via Verdi 1, Bergamo",
            ore_mensili_contratto=Decimal('20.00'),
            importo_mensile_contratto=Decimal('240.00'),  # 12 EUR/h -> sotto soglia 15 EUR/h
        )
        self.turno = Turno.objects.create(
            data=self.today,
            squadra=self.squadra,
        )
        self.assign = AssegnazioneTurno.objects.create(
            turno=self.turno,
            cliente=self.cliente,
            orario_inizio_previsto=datetime.time(8, 0),
            orario_fine_previsto=datetime.time(12, 0),
        )
        TimeTracking.objects.create(
            dipendente=self.dip,
            assegnazione=self.assign,
            ore_dichiarate=Decimal('4.50'),
            is_validated=True,
            note="Pulizia vetri",
        )
        Assenza.objects.create(
            dipendente=self.dip,
            data_inizio=datetime.date(2026, 5, 18),
            data_fine=datetime.date(2026, 5, 19),
            tipo='104',
            stato_approvazione='APPROVATA',
        )
        Assenza.objects.create(
            dipendente=self.dip,
            data_inizio=datetime.date(2026, 5, 20),
            data_fine=datetime.date(2026, 5, 20),
            tipo='FERIE',
            stato_approvazione='APPROVATA',
        )

    def test_1_single_source_of_truth_html_pdf_csv_and_104_fix(self):
        from core.paghe_service import calcola_dataset_paghe
        from core.models import ModificaCedolino

        qs = f"data_inizio={self.inizio_mese.isoformat()}&data_fine={self.fine_mese.isoformat()}"
        dataset = calcola_dataset_paghe(self.inizio_mese.isoformat(), self.fine_mese.isoformat())
        row = next(r for r in dataset['report_list'] if r['dip_id'] == self.dip.pk)

        self.assertEqual(row['ore_lavorate'], 4.5)
        self.assertEqual(row['ore_validate'], 4.5)
        self.assertEqual(row['giorni_lavorati'], 1)
        self.assertEqual(row['assenze_dict']['104'], 2)
        self.assertEqual(row['assenze_dict']['FERIE'], 1)
        self.assertEqual(row['altri_e_104'], 2)
        self.assertEqual(dataset['totale_generale']['altri_e_104_totali'], 2)

        # Verifica HTML
        res_html = self.client.get(f"/report-paghe/?{qs}")
        self.assertEqual(res_html.status_code, 200)

        # Verifica CSV (prima andava in crash con KeyError: 'ore_per_giorno')
        res_csv = self.client.get(f"/report-paghe/csv/?{qs}")
        self.assertEqual(res_csv.status_code, 200)
        csv_text = res_csv.content.decode('utf-8-sig')
        self.assertIn("Ratti;Claudio;RTTCLD80A01B157X", csv_text)
        self.assertIn("4,5", csv_text)

        # Verifica PDF (prima ignorava i giorni L.104 nella colonna Altri/104)
        res_pdf = self.client.get(f"/report-paghe/pdf/?{qs}")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(res_pdf.content.startswith(b'%PDF'))

        # Verifica override ModificaCedolino propagato identicamente a dataset, CSV e PDF
        ModificaCedolino.objects.create(
            dipendente=self.dip,
            data_inizio=self.inizio_mese,
            data_fine=self.fine_mese,
            ore_lavorate_override=10.0,
            ore_validate_override=10.0,
            giorni_104_override=3,
            note="Rettifica test",
        )
        dataset_mod = calcola_dataset_paghe(self.inizio_mese.isoformat(), self.fine_mese.isoformat())
        row_mod = next(r for r in dataset_mod['report_list'] if r['dip_id'] == self.dip.pk)
        self.assertTrue(row_mod['is_rettificato'])
        self.assertEqual(row_mod['ore_lavorate'], 10.0)
        self.assertEqual(row_mod['altri_e_104'], 3)
        self.assertEqual(dataset_mod['totale_generale']['altri_e_104_totali'], 3)

    def test_2_verifica_ore_analisi_contratti_e_reconciliation_unificati(self):
        # 1. Verifica Ore (HTML + PDF)
        res_vo = self.client.get('/verifica-ore/?mese=5&anno=2026')
        self.assertEqual(res_vo.status_code, 200)
        self.assertEqual(res_vo.context['totale_clienti']['ore_lavorate'], 4.5)

        res_vo_pdf = self.client.get('/pdf-verifica-ore/?mese=5&anno=2026')
        self.assertEqual(res_vo_pdf.status_code, 200)
        self.assertTrue(res_vo_pdf.content.startswith(b'%PDF'))

        # 2. Analisi Contratti (HTML + PDF) ora legge anche ore_dichiarate
        res_ac = self.client.get('/analisi-contratti/?mese=5&anno=2026&soglia=15')
        self.assertEqual(res_ac.status_code, 200)
        row_ac = res_ac.context['analisi'][0]
        self.assertEqual(row_ac['ore_lavorate'], '4.5h')
        self.assertTrue(row_ac['sotto_soglia'])

        res_ac_pdf = self.client.get('/analisi-contratti/pdf/?mese=5&anno=2026&soglia=15')
        self.assertEqual(res_ac_pdf.status_code, 200)
        self.assertTrue(res_ac_pdf.content.startswith(b'%PDF'))

        # 3. Reconciliation view legge anche ore_dichiarate
        res_rec = self.client.get('/reconciliation/?month=5&year=2026')
        self.assertEqual(res_rec.status_code, 200)
        rec_row = next(r for r in res_rec.context['report_data'] if r['cliente'].pk == self.cliente.pk)
        self.assertEqual(rec_row['ore_reali'], 4.5)









