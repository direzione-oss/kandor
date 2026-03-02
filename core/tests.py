
import datetime
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
        birthdays = context['birthdays']
        
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
