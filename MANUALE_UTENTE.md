# 📘 KANDOR — Manuale d'Uso Completo e Guida Operativa

> **Versione**: 3.1  
> **Ultimo aggiornamento**: 30 Ottobre 2026 (Selettore Rapido Mese/Settimana e Calendario Popover `🗓️ Mese ▾`, Inserimento e Validazione Diretta delle Ore da Amministrazione nel Modale Turno, Gestione Assenze e Sostituti nel Modale Turno, Preservazione Storico Turni Passati e Cedolini Chiusi per Squadre Eliminate e Dipendenti Licenziati/Inattivi, Contratto Part-Time `M`/`V`/`O`, 10 Corsi Sicurezza con Calcolo Automatico Scadenza, Scadenze ZTL Città Alta, Centro IA `/ia-hub/` con Barra Unificata Kandor Portal, Chat & Cedolini PDF)  
> **Applicazione Web Gestionale**: [kandor.187.126.30.207.sslip.io](https://kandor.187.126.30.207.sslip.io)  
> **Centro IA & Automazioni Smart**: [kandor.187.126.30.207.sslip.io/ia-hub/](https://kandor.187.126.30.207.sslip.io/ia-hub/)  
> **Web App Mobile Dipendenti**: [kandor.187.126.30.207.sslip.io/app/](https://kandor.187.126.30.207.sslip.io/app/)  
> **Sistema ERP per Imprese di Pulizie e Facility Management**

---

## 📋 Sommario Generale

1. [Introduzione e Architettura di Sistema](#1-introduzione-e-architettura-di-sistema)
2. [Accesso al Sistema e Sicurezza](#2-accesso-al-sistema-e-sicurezza)
3. [Dashboard Principale e Navigazione](#3-dashboard-principale-e-navigazione)
4. [Gestione Anagrafica Dipendenti, PIN App e Corsi](#4-gestione-anagrafica-dipendenti-pin-app-e-corsi)
5. [Gestione Anagrafica Clienti e Sedi](#5-gestione-anagrafica-clienti-e-sedi)
6. [Gestione Qualifiche e Competenze](#6-gestione-qualifiche-e-competenze)
7. [Gestione Parco Mezzi Aziendali e Permessi ZTL](#7-gestione-parco-mezzi-aziendali-e-permessi-ztl)
8. [Gestione Squadre Operative](#8-gestione-squadre-operative)
9. [Gestione Responsabili Area (RA)](#9-gestione-responsabili-area-ra)
10. [Pianificazione Turni, Calendario e Composizione Retroattiva](#10-pianificazione-turni-calendario-e-composizione-retroattiva)
11. [Programmazione Ricorrente Contratti](#11-programmazione-ricorrente-contratti)
12. [Richieste e Interventi Straordinari](#12-richieste-e-interventi-straordinari)
13. [Gestione Sostituti, Smart Score IA (0–100) e "Non Sostituito (Salto Turno)"](#13-gestione-sostituti-smart-score-ia-0100-e-non-sostituito-salto-turno)
14. [Registrazione Ore (Time Tracking), Conferma Squadra e Validazione 1-Click](#14-registrazione-ore-time-tracking-conferma-squadra-e-validazione-1-click)
15. [Verifica Ore Mensili e Riconciliazione Storica](#15-verifica-ore-mensili-e-riconciliazione-storica)
16. [Report Paghe, AI Revisore Ore, Buste Paga e Rettifiche Amministrative](#16-report-paghe-ai-revisore-ore-buste-paga-e-rettifiche-amministrative)
17. [Gestione Assenze, Avvallo e Sostituzioni Automatiche](#17-gestione-assenze-avvallo-e-sostituzioni-automatiche)
18. [Segnalazioni dagli Operatori e Triage Automatico IA](#18-segnalazioni-dagli-operatori-e-triage-automatico-ia)
19. [Riconciliazione Ore e Monitoraggio Cantieri](#19-riconciliazione-ore-e-monitoraggio-cantieri)
20. [Analisi Economica Contratti e Marginalità](#20-analisi-economica-contratti-e-marginalita)
21. [Centro IA & Automazioni Smart (`/ia-hub/`) — I 5 Moduli a Costo Zero](#21-centro-ia--automazioni-smart-ia-hub--i-5-moduli-a-costo-zero)
22. [Web App Mobile per Dipendenti (`/app/`), PIN 4 Cifre e Assistente Vocale IA](#22-web-app-mobile-per-dipendenti-app-pin-4-cifre-e-assistente-vocale-ia)
23. [Integrazione Bot Telegram e Linguaggio Naturale IA per Lavoratori](#23-integrazione-bot-telegram-e-linguaggio-naturale-ia-per-lavoratori)
24. [Messaggi Programmati e Comunicazioni di Massa](#24-messaggi-programmati-e-comunicazioni-di-massa)
25. [Centro Messaggi Unificato (Web App + Telegram) e Invio Allegati](#25-centro-messaggi-unificato-web-app--telegram-e-invio-allegati)
26. [Gestione Dati, Import/Export Excel e Backup](#26-gestione-dati-importexport-excel-e-backup)
27. [Widget Dashboard e Monitoraggio Scadenze](#27-widget-dashboard-e-monitoraggio-scadenze)
28. [FAQ, Risoluzione Problemi e Domande Frequenti](#28-faq-risoluzione-problemi-e-domande-frequenti)

---

## 1. Introduzione e Architettura di Sistema

### Scopo del Sistema
**KANDOR** è una piattaforma ERP (Enterprise Resource Planning) verticale appositamente progettata per coprire l'intero ciclo operativo di un'impresa di pulizie e servizi integrati (facility management). Il software unisce in un unico ambiente le esigenze contabili dell'amministrazione, l'automazione intelligente tramite Intelligenza Artificiale a costo zero e le necessità quotidiane dei responsabili di cantiere e dei lavoratori sul campo.

Con Kandor l'azienda ottiene:
- **Pianificazione automatizzata dei turni**: Trasformazione dei contratti cliente in calendarizzazioni settimanali o mensili senza inserimenti manuali ripetitivi.
- **Supporto ai contratti storici e in essere**: Generazione retroattiva dei turni passati con marcatura automatica delle ore in attesa di conferma.
- **Doppio Canale Mobile per i Dipendenti (Web App `/app/` + Bot Telegram)**: Gli operatori registrano le ore (anche con dettatura vocale IA), confermano i compagni di squadra o segnalano assenze sia tramite la Web App Mobile con PIN di 4 cifre sia tramite Bot Telegram.
- **Centro IA & Automazioni Smart a Costo Zero (`/ia-hub/`)**: Cinque motori algoritmici ed euristici integrati direttamente nel codice Python/Django (senza alcun abbonamento esterno né costi a consumo) per:
  1. **AI Revisore Ore & Auto-Validazione 1-Click** delle timbrature regolari;
  2. **Assistente Conversazionale NLP (Testo/Voce), Lettura Certificati/Documenti e Triage Segnalazioni**;
  3. **Smart Sostituzioni Predittive (Ranking 0–100)** basate su storico presenze sul cantiere, distanza km, monte ore settimanale, tasso di risposta e idoneità corsi/visita medica;
  4. **Compliance Guardian & Briefing Mattutino** (controllo preventivo permessi ZTL Bergamo Città Alta, mezzi, visite mediche e corsi speciali richiesti dal cantiere);
  5. **Controllo Marginalità, Burn-Rate e Lavori Extra Fatturabili** estratti automaticamente dalle note di fine turno.
- **Gestione Avvallo Assenze e Sostituzioni Complete (incluso "Non Sostituito / Salto Turno")**: Workflow autorizzativo da parte dell'amministrazione con ricerca ordinata dei sostituti oppure chiusura per salto turno concordato con evidenziazione rossa a calendario.
- **Elaborazione Prospetto Paghe e Rettifiche Admin**: Report per lo studio di consulenza del lavoro con audit IA pre-busta paga e possibilità per l'amministrazione di rettificare giorni, ore e assenze prima della stampa o dell'esportazione.

### Requisiti Tecnici
- **Browser consigliati**: Google Chrome, Mozilla Firefox, Microsoft Edge o Apple Safari (versione aggiornata).
- **Connessione**: Connessione Internet attiva per l'utilizzo Cloud su Render, oppure rete locale in caso di installazione desktop locale.
- **Dispositivi Mobili**: Qualsiasi smartphone Android o iOS tramite browser (`https://kandor.187.126.30.207.sslip.io/app/`) e/o l'app gratuita Telegram (`@kandor_gestionale_bot`).

---

## 2. Accesso al Sistema e Sicurezza

### Accesso alla Piattaforma Cloud
L'indirizzo di riferimento per accedere al gestionale da qualsiasi postazione web è:
👉 **[https://kandor.187.126.30.207.sslip.io](https://kandor.187.126.30.207.sslip.io)**

Qualora l'utente non sia ancora autenticato, il sistema reindirizzerà automaticamente alla pagina di Login protetta.

> ℹ️ **Nota sull'inattività dell'ambiente Cloud**:  
> Il server Cloud (piano gratuito Render) entra in modalità di sospensione automatica dopo 15 minuti di inattività. Quando si effettua il primo accesso della giornata, il caricamento iniziale potrebbe richiedere circa 45–60 secondi per il "risveglio" dell'applicazione. Una volta avviato, il sistema risponderà ad alta velocità.

### Avvio Rapido su Installazione Locale (Desktop)
In presenza di installazione locale sulla macchina aziendale:
1. Apri la cartella del progetto e fai doppio click sul file **`kandor_avvia.pyw`** (o in alternativa esegui il file **`start_app.bat`**).
2. Il server locale si avvia istantaneamente (utilizzando la modalità SQLite WAL ad alte prestazioni) e apre in automatico il browser all'indirizzo **`http://127.0.0.1:8000/`**.

### Procedura di Login
1. Digita il tuo **Nome utente** e la **Password** nei rispettivi campi.
2. Clicca sul pulsante azzurro **"Accedi"**.
3. Se le credenziali sono corrette, verrai reindirizzato al pannello principale della Dashboard.

### Modifica della Password Utente
Per garantire la sicurezza dell'account, si consiglia di modificare la password al primo accesso:
1. In alto a destra nella barra di navigazione, clicca sul tuo Nome Utente.
2. Nel menu a comparsa, seleziona **"Cambia password"**.
3. Inserisci la password attuale e successivamente la nuova password due volte per conferma.
4. Clicca su **"Cambia la mia password"**.

### Controllo Validazione e Gestione Errori nei Form
Durante l'inserimento o la modifica dei dati (anagrafiche dipendenti, clienti, mezzi, assenze, turni):
- **Evidenziazione Diretta dell'Errore**: In caso di dati errati, incompleti o duplicati (es. Codice Fiscale errato, Targa già esistente, date di licenziamento antecedenti all'assunzione), il sistema **non mostra mai schermate di errore generico (500)** e **non disconnette l'utente**.
- **Banner Informativo e Conservazione Dati**: Viene visualizzato un banner rosso in cima al form con il dettaglio dell'errore. L'utente rimane all'interno della pagina corrente mantenendo tutti i campi già compilati per poter effettuare immediatamente le correzioni necessarie.
- **Sanitizzazione Automatica**: I Codici Fiscali, le Partite IVA e le Targhe dei veicoli vengono automaticamente puliti da spazi bianchi superflui e convertiti in caratteri maiuscoli al momento del salvataggio.

![Validazione Form ed Evidenziazione Errori in Banner Rosso](screenshots/03_validazione_form_errore.png)

---

## 3. Dashboard Principale e Navigazione

La Dashboard di Kandor costituisce il centro di controllo di tutte le attività operative.

![Schermata Dashboard Principale Kandor ERP](screenshots/01_dashboard.png)

### Layout della Schermata
- **Barra Superiore di Navigazione e Azioni Rapide**: Mostra il logo Kandor, il nome dell'utente connesso e i pulsanti diretti ai moduli strategici:
  - 🤖 **Centro IA & Automazioni (`/ia-hub/`)**: Accesso diretto alla console dei 5 moduli di Intelligenza Artificiale e Smart Automation.
  - 📲 **App Dipendenti (`/app/`)**: Accesso rapido alla Web App Mobile per i lavoratori.
  - 📊 **Supervisione Titolari (`/titolari/`)**: Cruscotto direzionale sintetico per i titolari.
  - 💰 **Cedolini Paghe (`/report-paghe/`)**: Elaborazione mensile buste paga e AI Revisore Ore.
- **Barra Laterale Sinistra (Operazioni Frequenti)**: Contiene i link rapidi alle funzionalità usate più spesso:
  - 🔄 **Trova Jolly**: Ricerca rapida sostituti per cantiere con **Smart Score IA (0–100)**
  - 📊 **Riconciliazione**: Confronto ore contrattuali vs consuntivate
  - 📈 **Analisi Contratti**: Verifica redditività e contratti sotto soglia
  - 📥 **Gestione Dati**: Importazione ed esportazione file Excel/CSV
  - 📖 **Guide e Manuali**: Accesso alla documentazione completa (Admin + Dipendenti)
  - 💬 **Centro Messaggi**: Chat diretta bidirezionale unificata (Web App + Telegram)
  - ⚡ **Genera Turni**: Generazione automatica dei turni ordinari
  - 📄 **Vedi Report / Verifica Ore**: Report mensile ore e assenze con PDF
  - 💼 **Report Paghe**: Elaborazione prospetto paghe per il consulente del lavoro
- **Corpo Centrale**: Presenta il **Calendario Interattivo della Pianificazione Settimanale** e la suddivisione modulare per **Risorse Anagrafiche** (Dipendenti, Clienti, Qualifiche, Mezzi, Squadre, Responsabili Area, Corsi Formazione) e **Sezione Operativa** (Turni, Assenze, Time Tracking, Richieste Sostituzione, Segnalazioni).
- **Pannello Destro (Widget Dinamici)**: Contiene i box informativi ad aggiornamento automatico (Scadenze Veicoli e ZTL, Scadenze Visite Mediche, Scadenze Corsi di Formazione, Compleanni in arrivo, Feed Operativo e Scadenze Contratti).

---

## 4. Gestione Anagrafica Dipendenti, PIN App e Corsi

### Scopo Operativo
Il modulo Dipendenti censisce tutti i lavoratori aziendali, raccogliendo le informazioni anagrafiche, le credenziali di accesso alla Web App Mobile (**Codice Fiscale + PIN di 4 cifre**), il contatto Telegram, le qualifiche professionali, la sorveglianza sanitaria, i corsi di formazione obbligatori e la disponibilità ad effettuare sostituzioni d'emergenza.

### Percorso di Navigazione
👉 **Dashboard** → **Dipendenti** (oppure `/admin/core/dipendente/`)

### Guida Passo-Passo per l'Inserimento e la Gestione di un Dipendente
1. Clicca su **Dipendenti** e poi sul pulsante in alto a destra **"+ Aggiungi Dipendente"**.
2. **Dati Anagrafici e Foto Profilo**:
   - Inserisci **Nome** e **Cognome**.
   - **Foto Profilo**: Puoi caricare la fotografia del lavoratore (con strumento di ritaglio circolare integrato) oppure lasciare che sia il dipendente stesso a caricarla dalla propria Web App Mobile.
   - Inserisci il **Codice Fiscale** (16 caratteri alfanumerici).  
     *Automazione*: Se lasci il campo "Data di Nascita" vuoto, il sistema estrapolerà automaticamente la data di nascita corretta decodificando il Codice Fiscale.
   - Digita l'**Indirizzo di Residenza** completo (Via/Piazza, Numero Civico, CAP, Comune, Provincia).  
     *Automazione GPS*: Al salvataggio della scheda, Kandor invierà l'indirizzo al servizio di geocodifica integrato per calcolare la latitudine e la longitudine GPS. Tali coordinate sono indispensabili per calcolare i km di distanza quando si cercano sostituti per i cantieri.
3. **Contatti, Web App Mobile (PIN 4 cifre) e Telegram**:
   - Inserisci il **Telefono** e l'**Email** del lavoratore.
   - **PIN Accesso App Mobile (4 cifre)**:  
     - Al salvataggio di un nuovo dipendente, se il campo viene lasciato vuoto, il sistema **genera automaticamente un PIN numerico casuale di 4 cifre** (es. `4829`).  
     - L'amministratore può leggere o modificare manualmente il PIN in qualsiasi momento all'interno della scheda dipendente.  
     - Nella lista generale **Dipendenti**, la colonna **`🔑 PIN & App`** mostra in chiaro il PIN di 4 cifre di ciascun lavoratore insieme al pulsante rapido **`📲 App`** per aprire l'anteprima della Web App Mobile.  
     - **Rigenerazione Multipla del PIN**: Selezionando uno o più dipendenti nella lista e scegliendo dal menu *Azione* in alto **"🔑 Rigenera PIN 4 cifre (App Mobile)"**, il sistema assegna istantaneamente un nuovo PIN casuale.
   - **Telegram Chat ID**: Inserisci l'identificativo univoco dell'account Telegram del dipendente (opzionale se il lavoratore utilizza la Web App Mobile `/app/`).
4. **Competenze, Contratto Part-Time (`M` / `V` / `O`), Sostituzioni e Sorveglianza Sanitaria**:
   - **Tipologia Contratto e Part-Time**: Spuntando la casella **"Contratto Part-Time"** (`is_part_time`), diventa obbligatorio selezionare il **Tipo Part-Time** (`tipo_part_time`) tra:
     - **`M` — Part-Time Misto**
     - **`V` — Part-Time Verticale**
     - **`O` — Part-Time Orizzontale**
     *(Se si salva con "Contratto Part-Time" attivo senza specificare il tipo `M`, `V` o `O`, il form mostra un avviso di validazione invitando a selezionarlo).*
   - Seleziona le **Qualifiche Possedute** nella lista a scelta multipla (es. Pulizie Industriali, Uso Monospazzola, Trattamento Cotto).
   - Se il lavoratore è disponibile a coprire i turni dei colleghi assenti, spunta la casella **"Disponibile come Sostituto"**.
   - **Prossima scadenza visita medica**: Inserisci la data della prossima visita medica periodica obbligatoria. Il sistema attiverà automaticamente un alert nella Dashboard principale **20 giorni prima** della scadenza (ed evidenzierà in rosso le visite eventualmente scadute, bloccando o segnalando eventuali anomalie anche nel modulo *Compliance Guardian IA*).
5. **Corsi di Formazione e Sicurezza (D.Lgs. 81/08) con Calcolo Automatico Scadenza**:
   - In fondo alla scheda del dipendente (oppure dalla voce dedicata **Corsi Dipendenti** in Dashboard) sono precaricati i **10 corsi di formazione standard** con le rispettive durate di legge:
     1. *Corso sicurezza generale* (5 anni)
     2. *Corso Specifico Basso Rischio* (5 anni)
     3. *Movimentazione manuale dei carichi* (5 anni)
     4. *DPI 3 lavori in quota* (5 anni)
     5. *RLS* (5 anni)
     6. *Preposto* (2 anni)
     7. *Primo soccorso* (3 anni)
     8. *Piattaforme mobili (PLE)* (5 anni)
     9. *HACCP* (5 anni)
     10. *Antincendio livello 2* (5 anni)
   - **Calcolo Automatico della Scadenza**: Impostando lo stato su **`✅ Fatto`** e inserendo la **Data di Esecuzione**, Kandor calcola e compila **automaticamente la Data di Scadenza** dell'attestato sommando gli anni di validità previsti dal catalogo (con gestione automatica anche degli anni bisestili), attivando il monitoraggio nel widget Scadenze della Dashboard (**20 giorni prima** della scadenza), nel modulo *Compliance Guardian IA* e nel profilo della Web App del dipendente.
6. **Stato Operativo, Data Licenziamento e Tutela dello Storico Cedolini**:
   - Imposta lo stato su **Attivo** per i lavoratori in servizio regolare.
   - **Passaggio a Inattivo o Inserimento Data di Licenziamento**: Quando un lavoratore cessa il rapporto di lavoro (stato impostato su **Inattivo** e/o compilazione della **Data di Licenziamento**), Kandor **rimuove automaticamente il lavoratore soltanto dai turni futuri** (successivi ad oggi o alla data di licenziamento), **preservando integralmente tutti i turni passati, le timbrature (`TimeTracking`) e le assenze storiche**. In questo modo i cedolini paga dei mesi passati e del mese di cessazione rimangono completi ed esportabili in `/report-paghe/`.
7. Clicca **"Salva"** in basso a destra.

---

## 5. Gestione Anagrafica Clienti e Sedi

### Scopo Operativo
Anagrafica di tutti i clienti o cantieri aziendali presso i quali si svolgono i servizi di pulizia o manutenzione.

### Percorso di Navigazione
👉 **Dashboard** → **Clienti** (oppure `/admin/core/cliente/`)

### Descrizione dei Campi
- **Ragione Sociale**: Denominazione ufficiale dell'azienda cliente o del condominio/ente.
- **Partita IVA / Codice Fiscale**: Dati fiscali del cliente.
- **Indirizzo Sede / Cantiere**: Ubicazione esatta del cantiere. Come per i dipendenti, l'indirizzo viene geocodificato in coordinate GPS per calcolare le distanze dai lavoratori e viene analizzato dal *Compliance Guardian IA* per rilevare automaticamente i cantieri situati in **Bergamo Città Alta / ZTL**.
- **Nome Referente / Ruolo / Telefono**: Dati della persona di contatto in loco (es. Direttore di Cantiere, Amministratore di Condominio).
- **Data Nascita Referente**: Utilizzata dal widget della dashboard per segnalare i compleanni imminenti a scopo relazionale.
- **Ore Mensili Contratto**: Monte ore mensile pattuito nel contratto commerciale (utilizzato nel modulo di Riconciliazione Ore e nel calcolo del *Burn-Rate IA*).
- **Importo Mensile Contratto (€)**: Corrispettivo economico mensile fatturato al cliente (utilizzato nel modulo di Analisi Economica Contratti e nel controllo *Marginalità IA*).
- **Note / Mansioni Cantiere (`note_mansioni`)**: Indicazioni operative specifiche (es. *"Codice allarme 4321"*, *"Pulizia vetri con lavori in quota o piattaforma PLE"*). Il motore IA legge automaticamente queste note per verificare che gli operatori assegnati possiedano i corsi speciali richiesti.

### Sezioni Inline all'interno della Scheda Cliente
All'interno della scheda del cliente è possibile gestire direttamente:
- **Programmazione Ricorrente**: Definizione dei giorni e degli orari fissi di pulizia.
- **Richieste Straordinarie**: Interventi una tantum o lavori speciali richiesti dal cliente.

---

## 6. Gestione Qualifiche e Competenze

### Scopo Operativo
Le qualifiche rappresentano i requisiti tecnici e le idoneità professionali necessarie per eseguire determinati lavori nei cantieri.

### Percorso di Navigazione
👉 **Dashboard** → **Qualifiche** (oppure `/admin/core/qualifica/`)

### Utilizzo nel Sistema
- **Assegnazione al Dipendente**: Ogni lavoratore può possedere una o più qualifiche.
- **Requisito nella Programmazione**: Quando si definisce un lavoro per un cliente, è possibile specificare la qualifica obbligatoria.
- **Filtro nel "Trova Jolly"**: Quando si cerca un sostituto per un cantiere con qualifica speciale, l'algoritmo esclude automaticamente i dipendenti che non possiedono quella specifica qualifica.

---

## 7. Gestione Parco Mezzi Aziendali e Permessi ZTL

### Scopo Operativo
Monitoraggio e assegnazione dei veicoli commerciali e delle autovetture aziendali utilizzate dalle squadre per raggiungere i cantieri, con controllo completo delle scadenze amministrative e dei permessi ZTL.

### Percorso di Navigazione
👉 **Dashboard** → **Mezzi Aziendali** (oppure `/admin/core/mezzo/`)

### Descrizione dei Campi
- **Modello Mezzo**: Descrizione del veicolo (es. *Fiat Doblo 1.3 Multijet*).
- **Targa**: Targa del veicolo (univoca nel sistema).
- **Stato Attuale**: Selezionabile tra *Disponibile*, *In Manutenzione*, *Guasto / Fuori Uso*.
- **Km Percorsi**: Chilometraggio aggiornato del veicolo.
- **Scadenze & Permessi**:
  - **Scadenza Polizza Assicurativa**: Data di scadenza dell'assicurazione RCA.
  - **Scadenza Bollo**: Data di scadenza della tassa di circolazione.
  - **Scadenza Revisione**: Data di scadenza della revisione ministeriale periodica.
  - **Scadenza Permesso Città Alta (ZTL)**: Data di scadenza del permesso di transito/sosta in Zona a Traffico Limitato (Bergamo Città Alta).
  - **Numero Permesso Città Alta**: Codice identificativo / numero di contrassegno o pratica associato al permesso ZTL.

### Badge Semaforici nella Lista Mezzi, Alert Dashboard e Controllo IA ZTL
- Nella tabella **Mezzi Aziendali**, ogni scadenza (*Assicurazione*, *Bollo*, *Revisione*, *Permesso Città Alta*) viene mostrata con un **badge colorato semaforico**:
  - 🟢 **Verde**: Scadenza regolare (oltre 30 giorni).
  - 🟠 **Arancione (`⚠️ Xgg`)**: Scadenza imminente entro i prossimi 30 giorni, con indicazione dei giorni residui.
  - 🔴 **Rosso (`SCADUTA`)**: Scadenza superata da rinnovare con urgenza.
- Inoltre, il modulo **Compliance Guardian IA (`/ia-hub/`)** incrocia automaticamente i turni dei prossimi 7 giorni: se una squadra diretta in un cantiere di **Città Alta** ha assegnato un mezzo con permesso ZTL scaduto o mancante (o con revisione/polizza scaduta), segnala immediatamente il rischio di multa/blocco operativo.

---

## 8. Gestione Squadre Operative

### Scopo Operativo
Raggruppamento organizzativo dei dipendenti che lavorano abitualmente insieme nello stesso turno o cantiere.

### Percorso di Navigazione
👉 **Dashboard** → **Squadre** (oppure `/admin/core/squadra/`)

### Configurazione di una Squadra
1. **Nome Squadra**: Denominazione identificativa (es. *Squadra Alpha - Sanità*, *Squadra Notturna Uffici*).
2. **Caposquadra**: Selezione del dipendente con funzioni di coordinatore di squadra.
3. **Componenti**: Selezione multipla di tutti gli operatori che fanno parte della squadra.
4. **Responsabile Area Collegato**: Il sistema associa automaticamente la squadra al Responsabile Area che la supervisiona.

### Funzionalità Speciale: Messaggio di Gruppo alla Squadra
Dalla lista delle squadre, selezionando una squadra e scegliendo dal menu in basso **"💬 Invia Messaggio alla Squadra"**, l'amministrazione può inviare istantaneamente una comunicazione (Telegram + Web App) a tutti i componenti della squadra contemporaneamente.

### Protezione dello Storico Turni Passati in caso di Modifica o Eliminazione Squadra
- **Modifica Componenti della Squadra**: Quando aggiungi o rimuovi operatori da una squadra esistente, Kandor aggiorna i componenti solo per i turni correnti e futuri, **senza mai alterare i turni dei mesi passati (cedolini chiusi)**.
- **Eliminazione di una Squadra**: Se elimini una squadra non più operativa, il sistema **cancella unicamente i turni futuri non ancora svolti**, mentre **conserva intatti tutti i turni passati**, il nome storico della squadra (`nome_squadra`), i componenti presenti e le ore lavorate (`TimeTracking`), garantendo la totale integrità contabile dello storico aziendale.

---

## 9. Gestione Responsabili Area (RA)

### Scopo Operativo
I Responsabili Area costituiscono il livello intermedio di coordinamento tra l'amministrazione aziendale e le singole squadre operative sul territorio.

### Percorso di Navigazione
👉 **Dashboard** → **Responsabili Area** (oppure `/admin/core/responsabilearea/`)

### Ruolo nel Workflow Sostituzioni
Quando un dipendente risulta assente e si avvia la ricerca di un sostituto:
1. Il sistema individua qual è la squadra interessata dal turno scoperto.
2. Identifica il **Responsabile Area** associato a quella squadra.
3. Invia una notifica al Responsabile Area richiedendo la sua **autorizzazione/approvazione** o permettendo all'ufficio di gestire direttamente l'invio ordinato ai sostituti.

---

## 10. Pianificazione Turni, Calendario e Composizione Retroattiva

### Scopo Operativo
Pianificazione delle attività lavorative quotidiane con visualizzazione a calendario e gestione avanzata sia per la programmazione futura sia per la regolarizzazione dei contratti storici già avviati nel passato.

### Percorso di Navigazione
👉 **Dashboard** → **Turni** oppure **Pianificazione Settimanale** (Calendario Interattivo)

### Caratteristiche del Calendario Interattivo e Navigazione Rapida Mese/Settimana
- **Vista Oraria Settimanale**: Mostra tutti i turni disposti nei vari giorni della settimana con l'indicazione del cliente, della squadra e degli orari previsti.
- **Selettore Rapido Mese, Settimana e Mini-Calendario Mensile (`🗓️ Mese ▾`)**:
  - Oltre ai pulsanti **`← PREV`** e **`NEXT →`**, la barra del calendario integra:
    1. **Menu a tendina del Mese (`📅 Ottobre 2026 ▾`)**: Permette di saltare con un click a qualsiasi mese dell'anno (6 mesi precedenti e 6 mesi successivi).
    2. **Menu a tendina delle Settimane del Mese (`Sett: 26 Ott - 01 Nov ▾`)**: Elenca tutte le settimane che compongono il mese selezionato per aprirle istantaneamente.
    3. **Mini-Calendario Mensile Interattivo a Comparsa (`🗓️ Mese ▾`)**: Cliccando sul pulsante blu **`🗓️ Mese ▾`** si apre una griglia mensile interattiva completa (Lunedì–Domenica) con frecce `◀` / `▶` per sfogliare i mesi, evidenziazione della settimana attualmente aperta in blu e del giorno odierno in arancione. Cliccando su qualsiasi giorno del mini-calendario, il sistema apre subito quella settimana **mantenendo attivo l'eventuale filtro per Squadra** selezionato!
- **Badge di Stato delle Ore, delle Assenze e delle Sostituzioni sulle Card Turno**:
  - 🟢 **Verde (`✔ Xh`)**: Le ore lavorate sono state verificate e approvate dall'amministrazione.
  - 🟡 **Giallo / Ambra (`⏳ Xh`)**: Ore comunicate dal lavoratore via Web App o Telegram (o con differenza oraria rispetto al previsto) in attesa di convalida.
  - 🔴 **Rosso con punto esclamativo (`! Ore mancanti`)**: Turno passato i cui consuntivi non sono ancora stati inseriti; cliccando sulla card l'amministrazione può inserire e validare direttamente le ore.
  - 🟣 **Viola (`🏥 Malattia` / `🏖️ Ferie` / `🕐 Permesso` / `♿ Legge 104`)**: Indica che i componenti attivi del turno risultano assenti e non è ancora subentrato un sostituto.
  - 🔴 **Bordo/Badge Rosso `⏭️ Non Sostituito (Salto Turno)`**: Indica che un dipendente assente in quel turno non è stato sostituito per decisione dell'ufficio (mostrando il nome dell'assente e la motivazione registrata).

![Calendario Settimanale Turni con Selettore Rapido Mese/Settimana e Mini-Calendario Mensile Popover](screenshots/02_calendario_turni.png)

### Inserimento Diretto Ore da Amministrazione e Gestione Assenze/Sostituti nel Modale "Modifica Turno"
Cliccando su qualsiasi card turno nel Calendario Settimanale si apre la finestra modale **"✏️ Modifica Turno"**, che permette all'ufficio di gestire tutto da un'unica schermata senza cambiare pagina:
1. **Gestione Assenze e Sostituti Direttamente nell'Elenco Componenti del Turno**:
   - Nella sezione **"👥 Dipendenti presenti in questo turno"**, i dipendenti che hanno un'assenza registrata in quella data vengono evidenziati con un riquadro viola, il nome barrato e un badge indicante il tipo e lo stato dell'assenza (es. `🏥 Malattia — In attesa avvallo` oppure `🏖️ Ferie`).
   - Accanto al dipendente assente compaiono i pulsanti operativi immediati:
     - **`✅ Valida e Sostituisci`** (se l'assenza è ancora in attesa di avvallo): approva l'assenza con 1 click e apre subito la ricerca del sostituto ordinata per Smart Score IA.
     - **`👥 Scegli Sostituto`**: apre il selettore dei candidati Jolly disponibili per quel turno.
     - **`🏢 Conferma / Sostituto`**: permette all'ufficio di confermare direttamente un sostituto già contattato per le vie brevi.
   - Quando un sostituto è già stato confermato per quel turno, compare nell'elenco con il badge verde **`🔄 SOSTITUTO`** (indicando anche chi sostituisce) e il pulsante rapido per cambiarlo se necessario.
2. **Sezione "⏱ Ore Lavorate Dichiarate / Inserimento Diretto Amministrazione"**:
   - Anche quando il lavoratore **non ha ancora inviato le ore** da Telegram o Web App, la sezione delle ore è **sempre visibile e compilabile dall'Amministrazione** (con l'avviso azzurro: *"ℹ️ Il lavoratore non ha ancora inviato le ore: puoi inserirle e validarle direttamente qui dall'amministrazione"*).
   - Il campo **"Ore effettive"** viene precompilato automaticamente con le ore previste da contratto/turno (es. `4.0`), confrontandole in tempo reale con la durata programmata.
   - L'amministratore può digitare le ore effettivamente svolte (es. `4.5`), inserire una motivazione o nota nel campo **"📝 Note ore / Motivazione variazione o straordinario"** (es. *"Pulizia straordinaria vetrate ingresso richiesta dal cliente (+0.5h)"*) e cliccare direttamente sul pulsante verde **`✔ Salva e valida ore`**.
   - **Effetto Immediato**: Kandor crea e convalida automaticamente i record `TimeTracking` (`source='ADMIN'`, `is_validated=True`) per tutti i componenti attivi presenti nel turno (escludendo automaticamente gli assenti/deselezionati e includendo gli eventuali sostituti confermati!) e colora subito la card del turno in **verde (`✔ Validate`)** sul calendario.

![Modale Modifica Turno con Inserimento e Validazione Diretta Ore da Amministrazione e Gestione Assenze/Sostituti](screenshots/06_modale_turno_ore_admin.png)

### Generazione Automatica dei Turni
Dalla barra laterale, cliccando su **"⚡ Genera Turni"**, il sistema prende tutte le *Programmazioni Ricorrenti* attive dei clienti e genera automaticamente le assegnazioni per i **prossimi 7 giorni**, evitando la creazione di duplicati.

### Composizione Retroattiva per Contratti Storici e in Essere
Quando viene inserito un nuovo contratto o una nuova programmazione ricorrente che ha una **Data Inizio Contratto nel passato**:
1. Al momento del salvataggio, Kandor calcola e compone in automatico tutti i turni giorno per giorno a partire dalla data d'inizio storica fino ad oggi.
2. I turni passati nascono nello stato **"In attesa di conferma delle ore lavorate"** (evidenziati con l'icona rossa **`!`** sul calendario).
3. **Protezione dello Storico**: Se successivamente si modifica la programmazione di un contratto, il sistema rigenera soltanto i turni da oggi in poi, lasciando intatti e protetti i turni passati già convalidati.

---

## 11. Programmazione Ricorrente Contratti

### Scopo Operativo
Definizione delle regole di ripetizione periodica delle pulizie e dei servizi per ciascun cliente.

### Percorso di Navigazione
👉 **Scheda Cliente** → Sezione **Programmazione Ricorrente** oppure dal menu Admin `/admin/core/programmazionericorrente/`

### Parametri della Programmazione
- **Tipo Ripetizione**:
  - **Giornaliero / Settimanale**: Ripetizione in specifici giorni della settimana (es. tutti i Lunedì, Mercoledì e Venerdì).
  - **Bisettimanale**: Ripetizione a settimane alternate (calcolata a partire dalla Data Inizio Contratto).
  - **Mensile**: Ripetizione in un giorno fisso del mese (es. il giorno 1 o 15 di ogni mese).
- **Ora Inizio** e **Durata (ore)**:
  - *Calcolo Automatico*: Digitando l'Ora Inizio (es. `08:00`) e la Durata (es. `2.5`), il sistema calcola e imposta automaticamente l'**Ora Fine** (`10:30`).
- **Orario Flessibile**: Se spuntato, indica che la squadra può effettuare il turno in una fascia oraria libera della giornata.
- **Squadra Abituale** e **Mezzo Abituale**: Assegnazioni predefinite per la generazione automatica.
- **Periodo di Validità**: `Data Inizio Contratto` e `Data Fine Contratto` (se lasciata vuota, s'intende a tempo indeterminato).

---

## 12. Richieste e Interventi Straordinari

### Scopo Operativo
Gestione dei lavori extra-contrattuali o una tantum richiesti dai clienti (es. lavaggio vetrate straordinario, pulizia post-cantiere/ristrutturazione).

### Percorso di Navigazione
👉 **Scheda Cliente** → Sezione **Richieste Straordinarie**

### Inserimento di un Intervento Straordinario
1. Specifica la **Data Inizio** e la **Data Fine** dell'intervento.
2. Inserisci gli **Orari di Lavoro** previsti.
3. Compila la **Descrizione Attività** dettagliando le operazioni da svolgere e i prodotti necessari.
4. Assegna la squadra o il dipendente preposto.
5. Al termine delle attività, spunta la casella **"Completata"** per archiviare l'intervento ed includere le ore nelle rendicontazioni.

---

## 13. Gestione Sostituti, Smart Score IA (0–100) e "Non Sostituito (Salto Turno)"

### Scopo Operativo
Procedura d'emergenza guidata e potenziata dall'Intelligenza Artificiale per coprire rapidamente i turni rimasti scoperti a causa dell'assenza di un operatore, oppure per registrare formalmente il "Salto Turno / Non Sostituito".

### Percorso di Navigazione
👉 **Calendario Turni** → Clicca sul turno scoperto → **"🔄 Trova Sostituto"**  
oppure dalla barra laterale **"Trova Jolly"** (`/find-jolly/`) o da **Richieste Sostituzione** (`/admin/core/richiestasostituzione/`)

### Come Funziona il Ranking Predittivo "Smart Sostituzioni IA (0–100)"
Quando cerchi un sostituto o apri il modale di sostituzione dopo l'avvallo di un'assenza:
1. **Filtro Automatico di Idoneità**: Kandor esclude automaticamente i dipendenti non attivi, non abilitati come sostituti, in assenza/malattia/ferie o già impegnati in un altro turno sovrapposto negli stessi orari.
2. **Calcolo dello Smart Score IA (da 0 a 100 punti)**: Invece di basarsi solo sulla distanza in linea d'aria, il motore IA (`calcola_smart_score_sostituto`) assegna a ciascun candidato un punteggio da **0 a 100** combinando 5 fattori reali:
   - ⭐ **Conoscenza del Cantiere (fino a +30 pt)**: Quante volte il lavoratore ha già lavorato in passato presso quello specifico cliente (`TimeTracking` storici). Chi conosce già accessi, chiavi e mansioni viene premiato in cima alla classifica!
   - 📍 **Vicinanza Geografica GPS (fino a +25 pt)**: Distanza chilometrica tra la residenza del candidato e il cantiere.
   - ⚖️ **Equilibrio Monte Ore Settimanale (fino a +15 pt)**: Premia chi ha ancora margine orario nella settimana corrente, evitando di sovraccaricare di straordinari chi ha già superato le 36–40 ore.
   - ⚡ **Affidabilità e Tasso di Risposta (fino a +15 pt)**: Percentuale storica di sostituzioni accettate rispetto a quelle rifiutate/scadute.
   - 🛡️ **Idoneità Sicurezza e Corsi**: Verifica se il candidato ha la visita medica valida e i corsi speciali richiesti dal cantiere, mostrando eventuali avvisi preventivi.
3. **Ordinamento e Invio Notifiche Sequenziale o Assegnazione Diretta d'Ufficio**:
   - L'amministrazione vede i candidati già ordinati dal punteggio **Smart Score IA più alto** al più basso, completi di badge esplicativi.
   - Può **Confermare Direttamente d'Ufficio (`⚡ Conferma Diretta`)** un sostituto (es. dopo averlo sentito telefonicamente) oppure selezionare l'ordine di preferenza (1°, 2°, 3° scelta) e cliccare su **"📤 Invia Notifiche"** per contattarli via Telegram e Web App.

![Schermata Gestione Richieste Sostituzione](screenshots/02_gestione_sostituzioni.png)

### Gestione "⏭️ Non Sostituito (Salto Turno)"
Può capitare che, a fronte dell'assenza di un operatore, l'ufficio decida di **non inviare alcun sostituto** (ad esempio perché il resto della squadra riesce a coprire il servizio, oppure perché si è concordato con il cliente di saltare o posticipare il passaggio):
1. All'interno della finestra modale **Seleziona Sostituti** (oppure dalla lista **Richieste Sostituzione** in Admin), clicca sul pulsante rosso/ambra **"⏭️ Non Sostituito (Salto Turno)"**.
2. Inserisci la **Motivazione obbligatoria** nel campo dedicato (es. *"Servizio coperto dagli altri 2 componenti della squadra"* oppure *"Concordato salto turno con l'amministratore"*).
3. Confermando l'operazione:
   - La richiesta passa nello stato definitivo **`NON_SOSTITUITO` (`Non Sostituito / Salto Turno`)** e non invia ulteriori solleciti ai Jolly.
   - Sul **Calendario della Pianificazione Settimanale**, il blocco del turno viene evidenziato in **rosso** con il dettaglio del dipendente non sostituito e la motivazione registrata dall'ufficio.

---

## 14. Registrazione Ore (Time Tracking), Conferma Squadra e Validazione 1-Click

### Scopo Operativo
Consuntivazione delle ore di lavoro effettivamente svolte dagli operatori sul campo, verifica automatica della presenza dei compagni di squadra e relativo processo di approvazione contabile.

### Modalità di Registrazione delle Ore
Le ore possono entrare nel sistema attraverso **tre canali sincronizzati**:
1. **Via Web App Mobile (`/app/` — Fonte `WEBAPP`)**: L'operatore accede con Codice Fiscale + PIN di 4 cifre e salva le ore del turno direttamente dallo smartphone (tramite il modulo standard oppure dettando a voce con l'**Assistente Rapido IA**).
2. **Via Bot Telegram (`@kandor_gestionale_bot` — Fonte `TELEGRAM`)**: A fine giornata l'operatore seleziona il turno dal bot Telegram (oppure scrive una frase libera all'IA, es. *"Oggi 4 ore al Condominio Rossi"*) e conferma le ore svolte.
3. **Inserimento Manuale Admin (Fonte `ADMIN`)**: Dall'interfaccia di gestione `Time Tracking` o direttamente dal Calendario dei turni.

### Conferma Automatica Presenza Compagni di Squadra
Quando un turno è assegnato ad una **Squadra Operativa**:
- Al primo operatore della squadra che registra le ore (sia da **Web App Mobile** sia da **Telegram**) viene mostrato l'elenco dei compagni previsti in squadra in quella giornata.
- L'operatore conferma con una spunta chi era presente:
  - Per tutti i colleghi confermati **presenti**, Kandor **registra automaticamente le stesse ore provvisorie**, evitando doppi inserimenti.
  - Se un collega previsto viene deselezionato come **assente**, il sistema invia automaticamente una segnalazione all'amministrazione per verificare l'assenza non comunicata.

### Procedura di Validazione Rapida 1-Click (Singola o Massiva tramite IA)
- **Validazione Singola dal Calendario**: Nella vista **Pianificazione Settimanale**, cliccando sull'icona `✓` accanto al badge ambra **`⏳ Provvisorie: Xh`**, le ore del turno vengono convalidate al volo e diventano verdi **`✅ Validate: Xh`**.
- **Auto-Validazione Massiva 1-Click con AI Revisore Ore**: Dal **Centro IA (`/ia-hub/`)** o dalla pagina **Report Paghe (`/report-paghe/`)**, cliccando su **"⚡ Auto-Valida Ore Regolari (1-Click)"**, il motore IA approva istantaneamente tutte le timbrature del mese che risultano prive di anomalie e perfettamente coerenti con gli orari previsti e con la squadra.

---

## 15. Verifica Ore Mensili e Riconciliazione Storica

### Scopo Operativo
Pannello di controllo per la verifica globale delle ore lavorate, contrattuali e non validate relative a qualsiasi mese presente o passato.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Vedi Report** (oppure `/verifica-ore/`)

### Utilizzo del Report per la Verifica dei Mesi Precedenti
1. Dai menu a tendina in alto, seleziona il **Mese** e l'**Anno** da analizzare (es. *Ottobre 2026*).
2. Clicca sul pulsante **"Aggiorna"**.
3. Il sistema rielabora istantaneamente tutti i dati del mese selezionato presentando tre tabelle riassuntive:
   - **Tabella 1: Riepilogo per Cliente**: Confronto tra ore di contratto previste, ore effettivamente lavorate e validate, differenza in ore e valore economico.
   - **Tabella 2: Riepilogo per Squadra e Dipendente**: Dettaglio delle ore svolte da ogni singolo lavoratore suddivise per squadra.
   - **Tabella 3: Riepilogo Assenze del Mese**: Conteggio dettagliato per lavoratore dei giorni di assenza usufruiti nel mese (Malattia, Ferie, Permessi, Legge 104). Cliccando sul nome del dipendente si espande il dettaglio analitico di ciascun periodo di assenza.
4. **Stampa PDF**: Cliccando su **"📄 Scarica PDF"** viene generato il documento ufficiale stampabile con il riepilogo contabile completo.

---

## 16. Report Paghe, AI Revisore Ore, Buste Paga e Rettifiche Amministrative

### Scopo Operativo
Modulo dedicato all'elaborazione del prospetto retributivo mensile da trasmettere allo Studio del Consulente del Lavoro per la stampa delle buste paga, potenziato con il banner **AI Revisore Ore** e la possibilità di effettuare rettifiche amministrative.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Report Paghe** (oppure `/report-paghe/`)

### Banner "🕵️‍♂️ AI Revisore Ore & Auto-Validazione 1-Click"
In cima alla pagina **Elaborazione Cedolini Paghe** è integrato il pannello intelligente **AI Revisore Ore**, che analizza tutte le timbrature del periodo selezionato e mostra:
- Il numero di **Timbrature Regolari Auto-Validabili** (coerenti con orario previsto, squadra e assenze) con il pulsante verde **"⚡ Auto-Valida X Ore Regolari (1-Click)"** per approvarle tutte istantaneamente.
- Il numero di **Anomalie Rilevate dall'IA** (es. scostamenti >25% o >1h, disallineamenti tra colleghi della stessa squadra, conflitti tra ore dichiarate e giornata di assenza, sforamenti monte ore settimanale part-time), con link diretto al dettaglio nel Centro IA (`/ia-hub/`).

### Funzionalità di Rettifica Amministrativa ("✏️ Rettifica")
Qualora vi siano stati errori nella timbratura delle ore, omissioni o accordi correttivi dell'ultimo minuto:
1. Nella tabella del Report Paghe, individua la riga del dipendente interessato.
2. Nella colonna **Azione Admin** sulla destra, clicca sul pulsante **`✏️ Rettifica`**.
3. Si aprirà un modale interattivo denominato **"Rettifica Cedolino Paghe - [Nome Dipendente]"**.
4. **Campi di Override Modificabili**:
   - **Giorni Lavorati Override**: Inserisci il numero corretto di giornate lavorate nel mese.
   - **Ore Totali Override**: Inserisci le ore complessive rettificate.
   - **Ore Validate Override**: Correggi il totale delle ore validate.
   - **Giorni Ferie / Permessi / Malattia / 104 Override**: Rettifica i giorni di assenza del mese.
   - **Note Rettifica (Obbligatorio)**: Inserisci la motivazione amministrativa della modifica.
5. Clicca su **"💾 Salva Rettifica"**.
6. **Effetto Immediato**: La riga del dipendente mostrerà il badge **`✏️ Rettificato`**, la tabella aggiornerà istantaneamente i totali generali ed i KPI del mese e l'annotazione comparirà sia nel **PDF stampabile per il Consulente** sia nell'**Esportazione Excel/CSV**.

![Schermata Report Paghe e Modale Rettifica Cedolino](screenshots/04_report_paghe.png)

---

## 17. Gestione Assenze, Avvallo e Sostituzioni Automatiche

### Scopo Operativo
Censimento delle assenze dei lavoratori con workflow autorizzativo dell'amministrazione ed automazione della ricerca sostituti.

### Percorso di Navigazione
👉 **Dashboard** → **Assenze** (oppure `/admin/core/assenza/`)

### Workflow con Avvallo Amministrativo e Avvio Automatico Sostituzioni
1. **Segnalazione Assenza**: L'assenza per malattia, ferie, permesso o Legge 104 viene inviata dall'operatore via Web App Mobile (`/app/`), via Bot Telegram o registrata dall'amministrazione (anche tramite l'*Analizzatore Documenti IA*). Inizialmente nasce nello stato **"In Attesa Avvallo Amministrazione"**.
2. **Valutazione e Avvallo dell'Amministrazione**: L'amministratore verifica la richiesta e clicca su **"Approvata (Avvallata)"**.
3. **Avvio Automatico Procedura di Sostituzione**: Subito dopo l'avvallo dell'amministrazione, Kandor esamina tutti i turni in cui era programmato l'assente e apre la finestra pop-up con i candidati ordinati per **Smart Score IA (0–100)** (oppure permette di impostare il turno come **⏭️ Non Sostituito / Salto Turno**).

![Schermata Gestione Assenze e Avvallo Amministrazione](screenshots/05_gestione_assenze.png)

---

## 18. Segnalazioni dagli Operatori e Triage Automatico IA

### Scopo Operativo
Gestione delle comunicazioni di servizio, anomalie, carenza materiali o guasti inviati dai lavoratori dai cantieri, con classificazione automatica di priorità e categoria tramite Intelligenza Artificiale.

### Percorso di Navigazione
👉 **Dashboard** → **Segnalazioni** (`/admin/core/segnalazione/`) oppure **Centro IA** (`/ia-hub/` → scheda *2. Assistente NLP, Triage & Documenti*)

### Come Funziona il Triage Automatico IA delle Segnalazioni
Ogni volta che un lavoratore invia una segnalazione (dalla Web App Mobile `/app/` o dal Bot Telegram):
1. Il motore IA (`classifica_segnalazione`) analizza istantaneamente il testo e assegna:
   - **Livello di Urgenza**: `🚨 CRITICA`, `⚠️ ALTA`, `🟡 MEDIA` oppure `🟢 BASSA`.
   - **Categoria Operativa**: `SICUREZZA` (infortuni, rischi elettrici/chimici, allagamenti), `GUASTO_MACCHINARIO` (monospazzola, lavasciuga, aspirapolvere rotti), `MATERIALI_SCORTE` (prodotti, detergenti, sacchi o carta terminati), `ACCESSO_CHIAVI` (allarme, cancelli o chiavi bloccate), `QUALITA_CLIENTE` (lamentele o contestazioni).
   - **Azione Consigliata**: Suggerimento operativo immediato per l'ufficio.
2. Il tag di triage (es. `[IA Triage: CRITICA | SICUREZZA]`) viene salvato automaticamente nelle **Note Amministrazione** della segnalazione.
3. **Notifica Prioritaria Immediata**: Se la segnalazione è classificata con urgenza **CRITICA** o **ALTA**, Kandor invia subito un avviso prioritario su Telegram ai **Titolari** e ai **Responsabili Area**.

---

## 19. Riconciliazione Ore e Monitoraggio Cantieri

### Scopo Operativo
Controllo di gestione tra le ore pattuite a contratto con il cliente e le ore effettivamente lavorate e pagate al personale.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Riconciliazione** (oppure `/reconciliation/`)

### Indicatori di Scostamento
La tabella di riconciliazione evidenzia i cantieri con codici colore:
- 🟢 **Verde (Soglia OK)**: Le ore effettive scostano di meno di ±5 ore rispetto al contratto.
- 🟠 **Arancione (Warning - Eccesso Ore)**: Sono state lavorate più di +5 ore rispetto al pattuito (rischio di calo di marginalità se non fatturate extra).
- 🔴 **Rosso (Alarm - Carenza Ore)**: Sono state svolte meno di −5 ore rispetto al contratto (rischio di contestazione da parte del cliente per servizio incompleto).

---

## 20. Analisi Economica Contratti e Marginalità

### Scopo Operativo
Modulo di analisi finanziaria per identificare i contratti clienti che risultano sotto la soglia di redditività economica aziendale.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Analisi Contratti** (oppure `/analisi-contratti/`)

### Report di Redditività
Il sistema confronta l'importo mensile fatturato al cliente con il monte ore lavorato sul cantiere:
- Calcola la **Resa Oraria Effettiva (€/ora)** per ciascun cantiere.
- Segnala con alert visivi i contratti che generano un margine inferiore alla soglia minima impostata.
- Permette di esportare il **Report Economico in PDF** per le riunioni di direzione.

---

## 21. Centro IA & Automazioni Smart (`/ia-hub/`) — I 5 Moduli a Costo Zero

### Scopo Operativo e Architettura "100% Zero-Cost"
Il **Centro IA & Automazioni Smart** raccoglie in un'unica console direzionale tutti i **5 moduli di Intelligenza Artificiale ed Euristica Avanzata** progettati specificamente per Kandor.

> 💡 **Perché funziona a Costo Zero (0 €/mese)?**  
> Tutti i calcoli predittivi, le regole di audit, il parser del linguaggio naturale italiano e l'incrocio dei dati girano **localmente nel motore Python di Kandor (`core/ai_engine.py`)** interrogando direttamente il database aziendale, senza dipendere da abbonamenti a pagamento.  
> In più, il sistema è già predisposto in **modalità ibrida opzionale**: se in futuro viene inserita una chiave gratuita `GEMINI_API_KEY` di Google AI Studio, Kandor attiva automaticamente anche il supporto generativo *Gemini Flash* mantenendo sempre il motore locale come garanzia di funzionamento al 100%.

### Percorso di Navigazione e Nuova Barra Superiore Unificata "Kandor Portal"
👉 **Dashboard Principale** → Pulsante in alto **`🤖 Centro IA & Automazioni`** (oppure direttamente all'indirizzo **`https://kandor.187.126.30.207.sslip.io/ia-hub/`**)
- La pagina del **Centro IA (`/ia-hub/`)** integra ora la barra superiore istituzionale **Kandor Portal** con il Logo ufficiale Kandor, i collegamenti rapidi a **`🏠 Home`**, **`💬 Chat Telegram`**, **`💰 Cedolini Paghe`**, **`Modifica password`** e la barra breadcrumb di navigazione (`Home › Centro IA & Automazioni Smart`).

![Schermata Centro IA & Automazioni Smart (/ia-hub/) con i 5 Moduli e Barra Superiore Kandor Portal](screenshots/07_ia_hub.png)

### Guida Dettagliata alle 5 Schede del Centro IA

#### Modulo 1 — 🕵️‍♂️ Revisore Ore, Paghe & Auto-Validazione 1-Click
Scansiona tutte le assegnazioni e le timbrature (`TimeTracking`) del periodo selezionato effettuando 5 controlli incrociati:
1. **Scostamento Orario Significativo**: Segnala se un dipendente dichiara più del ±25% (o oltre ±1 ora) rispetto alla durata prevista del turno senza note giustificative.
2. **Disallineamento tra Compagni di Squadra**: Intercetta i casi in cui due membri della stessa squadra sullo stesso cantiere dichiarano durate diverse tra loro.
3. **Conflitto Ore Lavorate / Assenza**: Segnala con gravità **CRITICA** se un lavoratore ha ore registrate in un giorno in cui risulta in Malattia, Ferie o Permesso giornaliero.
4. **Sforamento Monte Ore Settimanale Part-Time**: Avvisa quando il cumulo settimanale di un operatore supera il tetto previsto dal suo contratto.
5. **Turni Passati Non Compilati**: Elenca i turni già svolti in cui nessun componente della squadra ha ancora inserito le ore.
- **Pulsante `⚡ Auto-Valida Tutte le Ore Regolari (1-Click)`**: Convalida in blocco tutte le timbrature che hanno superato i 5 controlli senza anomalie, risparmiando ore di spunta manuale a fine mese.

#### Modulo 2 — 💬 Assistente NLP, Triage Segnalazioni & Analizzatore Documenti
Include tre strumenti intelligenti:
1. **Assistente Conversazionale NLP (Telegram + Web App `/app/`)**: Permette agli operatori di scrivere o dettare a voce frasi naturali (es. *"Oggi 4 ore al Condominio Rossi"*, *"Domani sono in malattia"*) preparando l'operazione pronta da confermare.
2. **📄 Analizzatore Intelligente Documenti, Certificati Medici & Attestati**:
   - Incollando il testo (o l'esito OCR) di un certificato medico INPS, di un verbale di idoneità sanitaria o di un attestato di formazione e selezionando il dipendente:
   - L'IA riconosce il **Tipo di Documento**, estrae le **Date di Inizio/Fine** o la **Data di Scadenza** e il **Numero di Protocollo PUC**.
   - Spuntando **"Applica subito in automatico"**, Kandor **crea direttamente l'assenza per Malattia** (o **aggiorna la data di scadenza della Visita Medica** nella scheda del dipendente) con un solo click!
3. **🚨 Tabella Triage Automatico Segnalazioni Cantiere**: Mostra le ultime segnalazioni inviate dai lavoratori classificate per **Urgenza IA** (`CRITICA`, `ALTA`, `MEDIA`, `BASSA`), **Categoria IA** e **Azione Consigliata**.

#### Modulo 3 — 🎯 Smart Sostituzioni Predittive (Smart Score 0–100)
Riepiloga le richieste di sostituzione recenti e collega direttamente al motore **Trova Sostituto (`/find-jolly/`)** dove ogni candidato Jolly viene classificato con un punteggio predittivo da **0 a 100** basato su storico presenze nel cantiere, distanza km, carico orario settimanale, affidabilità storica e idoneità corsi/visita medica.

#### Modulo 4 — 🛡️ Compliance Guardian (ZTL Città Alta, Mezzi, Corsi) & Briefing Mattutino
Analizza preventivamente tutti i turni programmati nei **prossimi 7 giorni** per azzerare il rischio di multe o sanzioni ispettive:
- **Controllo ZTL Bergamo Città Alta**: Verifica se un turno presso un cliente situato in *Città Alta / ZTL* ha un mezzo assegnato con **Permesso Città Alta scaduto o mancante**.
- **Controllo Scadenze Mezzi in Turno**: Segnala se il furgone assegnato a una squadra ha l'**Assicurazione** o la **Revisione scaduta**, offrendo il pulsante rapido **`🔧 Metti Mezzo in Manutenzione`** per bloccarlo in 1 click.
- **Controllo Visita Medica e Corsi Speciali Cantiere**: Verifica se gli operatori in turno hanno la visita medica scaduta o se mancano dei corsi specifici richiesti dalle note mansioni del cantiere (es. *DPI 3 Lavori in Quota*, *Piattaforme Mobili PLE*, *HACCP*, *Antincendio*).
- **☀️ Briefing Operativo Mattutino (`📲 Invia Briefing su Telegram`)**: Genera il bollettino direzionale della giornata e permette di inviarlo con un click su Telegram ai Titolari.

#### Modulo 5 — 📈 Controllo Marginalità, Burn-Rate e Lavori Extra Fatturabili
Offre il controllo economico in tempo reale su tutti i cantieri attivi nel mese:
- **💰 Lavori Extra Fatturabili Rilevati dalle Note**: L'IA legge tutte le note inserite dai dipendenti a fine turno (`TimeTracking.note`) e intercetta parole chiave di lavori straordinari o fuori capitolato (*"extra"*, *"allagamento"*, *"emergenza"*, *"sgombero"*, *"vetri extra"*, *"richiesto dal cliente"*), elencandole pronte per essere fatturate a parte dall'amministrazione.
- **📊 Tabella Burn-Rate & Proiezione Sforamento Mensile**: Per ogni cliente confronta le **Ore Contratto Mensili**, le **Ore Già Lavorate**, la **Proiezione Matematica a Fine Mese** (in base ai giorni trascorsi), lo **Scostamento Stimato** e la **Resa Oraria Effettiva (€/h)**, segnalando con semaforo 🔴 **SFORAMENTO CRITICO** o 🟠 **ATTENZIONE** i cantieri che stanno consumando il budget troppo velocemente.

---

## 22. Web App Mobile per Dipendenti (`/app/`), PIN 4 Cifre e Assistente Vocale IA

### Scopo Operativo
Fornire a tutti i dipendenti un'applicazione mobile completa (Progressive Web App — PWA), installabile sulla schermata Home dello smartphone (Android e iPhone) **senza bisogno di avere Telegram**, dotata anche di **Assistente Rapido IA con dettatura vocale**.

### Indirizzo Ufficiale e Credenziali di Accesso
- **URL per i Dipendenti**: 👉 **[https://kandor.187.126.30.207.sslip.io/app/](https://kandor.187.126.30.207.sslip.io/app/)**
- **Credenziali del Lavoratore**:
  1. **Codice Fiscale** (16 caratteri alfanumerici).
  2. **PIN personale di 4 cifre** (`pin_accesso`), visibile e gestibile dall'amministrazione nella colonna **`🔑 PIN & App`** della lista Dipendenti.

### 🤖 Assistente Rapido IA (Testo o Voce) nella Web App
In cima alla scheda principale **⏱ Oggi & Ore**, il dipendente trova il box **"🤖 Assistente Rapido IA (Testo o Voce)"**:
- Toccando il pulsante del **microfono `🎙️`** (Dettatura Vocale nativa dello smartphone) oppure scrivendo nella casella, il lavoratore può dire o digitare una frase naturale come:
  - *"Oggi 4 ore da Condominio Rossi"* → L'IA compila e registra direttamente le ore sul turno corrispondente!
  - *"Domani sono in malattia"* → L'IA prepara la richiesta di assenza.
  - *"È finita la candeggina in cantiere"* → L'IA crea la segnalazione con Triage automatico per l'ufficio.

### Le 5 Schede Operative della Web App Mobile
1. **⏱ Oggi & Ore**:
   - Box **🤖 Assistente Rapido IA (Testo o Voce)**.
   - Riepilogo mensile in tempo reale (*Ore Validate ✅*, *In Attesa ⏳*, *Totale Mese*).
   - Elenco dei turni della giornata con pulsante **`⏱ Inserisci Ore`** (che apre e scorre automaticamente al modulo di inserimento ore del turno), indirizzo con **📍 Apri Mappa (Google Maps)** e **conferma presenza dei compagni di squadra**.
   - Sezione **📋 Turni da Compilare (Ultimi 7 Giorni)** per recuperare i turni passati dimenticati.
2. **📅 Calendario**:
   - Navigatore giornaliero (`◀ Prec.` / `Oggi` / `Succ. ▶`) e panoramica completa dei turni programmati nei **prossimi 7 giorni**.
3. **🏥 Assenze**:
   - Invio immediato di comunicazioni per **Malattia**, **Ferie**, **Permesso Orario** e **Legge 104**, più storico delle richieste con stato di avvallo in tempo reale (*In attesa di avvallo*, *Approvata*, *Rifiutata*).
4. **💬 Ufficio (Chat Diretta & Segnalazioni con Triage IA)**:
   - **Chat Bidirezionale**: Messaggistica istantanea con l'amministrazione con invio di **foto o allegati PDF** e download di documenti/cedolini inviati dall'ufficio.
   - **🚨 Segnalazioni Cantiere**: Modulo per segnalare guasti o anomalie (classificate automaticamente dal Triage IA) e consultare lo stato di risoluzione.
5. **👤 Profilo & 🔄 Sostituzioni**:
   - Caricamento/aggiornamento della **Foto Profilo** (con avatar automatico su iniziali in caso di assenza foto).
   - Visualizzazione scadenze della **Visita Medica** e dei **Corsi di Formazione**.
   - **Banner Sostituzioni Urgenti**: Avviso interattivo in cima all'app con i pulsanti **`✅ Accetta Sostituzione`** e **`❌ Rifiuta`**.

![Panoramica Schermate Web App Mobile Dipendenti Kandor (/app/)](screenshots/08_webapp_dipendente.png)

---

## 23. Integrazione Bot Telegram e Linguaggio Naturale IA per Lavoratori

### Scopo Operativo
Fornire ai lavoratori che utilizzano Telegram uno strumento immediato sul proprio smartphone, utilizzabile sia tramite **menu a bottoni** sia scrivendo **frasi libere in linguaggio naturale** grazie al motore IA integrato.

### Nome e Contatto del Bot
- Nome Bot: **Kandor Assistente** (`@kandor_gestionale_bot`)
- Link di avvio: **[https://t.me/kandor_gestionale_bot](https://t.me/kandor_gestionale_bot)**

### Bottoni del Menu Principale e Assistente IA su Telegram
- **Menu a Bottoni**: `⏱ Registra Ore`, `📋 Turni Non Compilati`, `📅 I Miei Turni`, `🤒 Malattia / Ferie / Permesso`, `⚠️ Segnalazione`, `📖 Guida`.
- **Comprensione Frasi Libere con Conferma in 1 Click**: Se il lavoratore scrive direttamente in chat una frase come *"Oggi ho fatto 4 ore"* oppure *"Domani sono in malattia"*, l'IA di Kandor comprende l'intenzione e risponde mostrando un **bottone di conferma rapida in 1 click** (es. **`✅ Conferma 4.0h su Condominio Rossi`** oppure **`✅ Conferma MALATTIA (24/10 - 24/10)`**), registrando l'operazione istantaneamente appena il dipendente tocca il bottone!

---

## 24. Messaggi Programmati e Comunicazioni di Massa

### Scopo Operativo
Pianificazione dell'invio differito di comunicazioni, circolari o allegati PDF (es. cedolini, avvisi) ai lavoratori.

### Percorso di Navigazione
👉 **Dashboard** → **Messaggi Programmabili** (oppure `/admin/core/messaggioprogrammato/`)

### Configurazione Invio
1. Inserisci il **Titolo**, il **Testo del Messaggio** ed eventualmente carica un **File Allegato**.
2. Imposta la **Data e Ora di Invio** programmata.
3. Seleziona i **Destinatari Specifici** oppure spunta la casella **"Invia a TUTTI"** per raggiungere l'intero organico attivo.
4. Il sistema eseguirà l'invio automatico all'orario stabilito.

---

## 25. Centro Messaggi Unificato (Web App + Telegram) e Invio Allegati

### Scopo Operativo
Console di messaggistica bidirezionale in tempo reale per conversare direttamente con tutti i dipendenti attivi (sia quelli che usano la **Web App Mobile `/app/`**, sia quelli collegati a **Telegram**) senza uscire dall'interfaccia di Kandor.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Centro Messaggi** (oppure `/chat-simulator/`)

### Funzionalità della Chat Unificata
- **Lista Completa Dipendenti Attivi**: Elenco a sinistra di tutti i lavoratori attivi con badge rosso per i messaggi non letti, anche per chi utilizza esclusivamente la Web App Mobile senza Telegram.
- **Invio e Ricezione Allegati (PDF, Cedolini, Foto)**: L'amministrazione può allegare documenti PDF (es. buste paga, CU, circolari) o immagini; il lavoratore li riceve sia su Telegram sia nella scheda **💬 Ufficio** della Web App Mobile.
- **Visualizzazione Foto dai Cantieri**: Possibilità di ingrandire e scaricare le foto inviate dagli operatori tramite Web App o Telegram.
- **Invio Broadcast / Per Squadra**: Pulsanti dedicati per inviare comunicazioni istantanee ad una specifica squadra o a tutti i lavoratori.

---

## 26. Gestione Dati, Import/Export Excel e Backup

### Scopo Operativo
Strumenti di caricamento massivo dati da fogli di calcolo e salvataggio di sicurezza dell'intero database aziendale.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Gestione Dati** (oppure `/data-management/`)

### Importazione da Excel
1. Scarica i **Template Excel ufficiali** (Dipendenti, Clienti, Mezzi, Qualifiche).
2. Compila le colonne rispettando i formati indicati.
3. Carica il file selezionando la modalità:
   - **AGGIORNA**: Aggiorna i record esistenti e crea quelli nuovi.
   - **SOVRASCRIVI**: Sostituisce integralmente la tabella.

### Backup e Ripristino Database (Riservato a Superuser)
- **Crea Backup**: Genera e scarica un file JSON contenente l'intera banca dati di Kandor.
- **Ripristina Backup**: Permette di caricare un file JSON di backup precedentemente salvato per ripristinare il sistema.

---

## 27. Widget Dashboard e Monitoraggio Scadenze

Il pannello informativo destro della Dashboard include widget ad aggiornamento automatico:

1. 🚗 **Scadenze Veicoli & Permessi ZTL Città Alta**:
   - Visualizza i veicoli con **Assicurazione**, **Bollo**, **Revisione** o **Permesso ZTL Città Alta** (con relativo numero permesso) in scadenza nei successivi 45 giorni (colore arancione) o già scaduti (colore rosso).
2. 🩺 **Scadenze Visite Mediche**:
   - Segnala automaticamente i dipendenti attivi con **Prossima scadenza visita medica** entro i successivi **20 giorni** (in arancione) o già scaduta (in rosso), con collegamento diretto alla scheda del lavoratore.
3. 🎓 **Scadenze Corsi di Formazione**:
   - Monitora gli attestati di sicurezza dei lavoratori (*Primo Soccorso*, *Antincendio*, *Formazione Specifica*, *Lavori in Quota*, *PLE*, *HACCP*, ecc.) evidenziando quelli in scadenza entro **30 giorni** o scaduti.
4. 🎂 **Compleanni in Arrivo**:
   - Mostra i compleanni dei dipendenti e dei referenti clienti nei successivi 20 giorni.
5. 📅 **Pianificazione Settimanale**:
   - Calendario interattivo dei turni con stato delle ore, sostituzioni, salti turno in rosso e navigazione rapida.
6. 📱 **Feed Operativo (Web App & Telegram)**:
   - Flusso in tempo reale degli ultimi messaggi, timbrature e segnalazioni ricevute dagli operatori.

---

## 28. FAQ, Risoluzione Problemi e Domande Frequenti

### ❓ I 5 moduli di Intelligenza Artificiale (`/ia-hub/`) hanno un costo mensile o a consumo?
**Risposta**: **No, sono 100% gratuiti e senza alcun costo ricorrente.** L'intero motore IA (`core/ai_engine.py`) è stato sviluppato con algoritmi matematici, regole euristiche e parser NLP in lingua italiana che girano direttamente dentro il server di Kandor. Anche la dettatura vocale nella Web App utilizza le API native gratuite dello smartphone.

### ❓ Come funziona l'Auto-Validazione 1-Click delle ore con l'IA?
**Risposta**: Dal **Centro IA (`/ia-hub/`)** o dalla pagina **Report Paghe (`/report-paghe/`)**, l'**AI Revisore Ore** controlla tutte le timbrature del periodo. Quelle che coincidono con l'orario previsto (entro le soglie di tolleranza), che sono allineate con i compagni di squadra e prive di conflitti con assenze vengono marcate come **Regolari Auto-Validabili**: basta cliccare su **"⚡ Auto-Valida Ore Regolari (1-Click)"** per convalidarle tutte insieme, concentrandosi solo sulle eventuali anomalie segnalate.

### ❓ Cosa devo fare se un dipendente è assente ma decidiamo di NON mandare un sostituto (Salto Turno)?
**Risposta**: Quando si apre il modale di sostituzione (o dalla sezione *Richieste Sostituzione*), clicca sul pulsante **"⏭️ Non Sostituito (Salto Turno)"** e inserisci la motivazione. La richiesta verrà chiusa come `NON_SOSTITUITO` e sul calendario il turno apparirà evidenziato in **rosso** con il nome dell'assente non sostituito e la nota inserita.

### ❓ Un dipendente non ha Telegram. Come può registrare le ore e comunicare con l'ufficio?
**Risposta**: Può utilizzare la **Web App Mobile Dipendenti** all'indirizzo **`https://kandor.187.126.30.207.sslip.io/app/`** entrando con il suo **Codice Fiscale** e il **PIN di 4 cifre** visibile nella colonna **`🔑 PIN & App`** della lista Dipendenti. Dall'app può anche usare il microfono dell'**Assistente Rapido IA** per dettare a voce le ore lavorate!

### ❓ Dove trovo o come cambio il PIN di 4 cifre di un dipendente?
**Risposta**: Vai in **Dashboard → Dipendenti**: nella tabella vedrai la colonna **`🔑 PIN & App`** con il codice di 4 cifre di ciascun lavoratore. Puoi cambiarlo aprendo la scheda del dipendente oppure rigenerarlo in automatico selezionando il dipendente e usando l'azione **"🔑 Rigenera PIN 4 cifre (App Mobile)"**.

### ❓ Perché nel report delle buste paga le ore non corrispondono con quelle che dichiara il dipendente?
**Risposta**: Il report contabile contabilizza soltanto le **ore convalidate** (badge verde). Se il dipendente ha inserito le ore ma l'amministrazione non le ha ancora convalidate (badge ambra ⏳), puoi approvarle in blocco con il bottone **⚡ Auto-Valida Ore Regolari (1-Click)** oppure intervenire tramite il pulsante **`✏️ Rettifica`** per impostare gli override correttivi.

---

> **KANDOR ERP** — Gestionale Operativo con Intelligenza Artificiale Integrata per Imprese di Servizi  
> *Sviluppato da Studio Serra — Versione 3.1 (30/10/2026) — © 2026*
