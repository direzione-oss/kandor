# 📘 KANDOR — Manuale d'Uso Completo e Guida Operativa

> **Versione**: 2.6  
> **Ultimo aggiornamento**: Ottobre 2026 (Integrazione Avvallo Sostituzione & Validazione Form)  
> **Applicazione Web**: [kandor.onrender.com](https://kandor.onrender.com)  
> **Sistema ERP per Imprese di Pulizie e Facility Management**

---

## 📋 Sommario Generale

1. [Introduzione e Architettura di Sistema](#1-introduzione-e-architettura-di-sistema)
2. [Accesso al Sistema e Sicurezza](#2-accesso-al-sistema-e-sicurezza)
3. [Dashboard Principale e Navigazione](#3-dashboard-principale-e-navigazione)
4. [Gestione Anagrafica Dipendenti](#4-gestione-anagrafica-dipendenti)
5. [Gestione Anagrafica Clienti e Sedi](#5-gestione-anagrafica-clienti-e-sedi)
6. [Gestione Qualifiche e Competenze](#6-gestione-qualifiche-e-competenze)
7. [Gestione Parco Mezzi Aziendali](#7-gestione-parco-mezzi-aziendali)
8. [Gestione Squadre Operative](#8-gestione-squadre-operative)
9. [Gestione Responsabili Area (RA)](#9-gestione-responsabili-area-ra)
10. [Pianificazione Turni, Calendario e Composizione Retroattiva](#10-pianificazione-turni-calendario-e-composizione-retroattiva)
11. [Programmazione Ricorrente Contratti](#11-programmazione-ricorrente-contratti)
12. [Richieste e Interventi Straordinari](#12-richieste-e-interventi-straordinari)
13. [Gestione Sostituti e Ricerca "Trova Jolly"](#13-gestione-sostituti-e-ricerca-trova-jolly)
14. [Registrazione Ore (Time Tracking) e Validazione 1-Click](#14-registrazione-ore-time-tracking-e-validazione-1-click)
15. [Verifica Ore Mensili e Riconciliazione Storica](#15-verifica-ore-mensili-e-riconciliazione-storica)
16. [Report Paghe, Buste Paga e Rettifiche Amministrative](#16-report-paghe-buste-paga-e-rettifiche-amministrative)
17. [Gestione Assenze, Avvallo e Sostituzioni Automatiche](#17-gestione-assenze-avvallo-e-sostituzioni-automatiche)
18. [Segnalazioni dagli Operatori](#18-segnalazioni-dagli-operatori)
19. [Riconciliazione Ore e Monitoraggio Cantieri](#19-riconciliazione-ore-e-monitoraggio-cantieri)
20. [Analisi Economica Contratti e Marginalità](#20-analisi-economica-contratti-e-marginalita)
21. [Integrazione Bot Telegram per Lavoratori](#21-integrazione-bot-telegram-per-lavoratori)
22. [Messaggi Programmati e Comunicazioni di Massa](#22-messaggi-programmati-e-comunicazioni-di-massa)
23. [Centro Messaggi e Chat Bidirezionale Telegram](#23-centro-messaggi-e-chat-bidirezionale-telegram)
24. [Gestione Dati, Import/Export Excel e Backup](#24-gestione-dati-importexport-excel-e-backup)
25. [Widget Dashboard e Monitoraggio Scadenze](#25-widget-dashboard-e-monitoraggio-scadenze)
26. [FAQ, Risoluzione Problemi e Domande Frequenti](#26-faq-risoluzione-problemi-e-domande-frequenti)

---

## 1. Introduzione e Architettura di Sistema

### Scopo del Sistema
**KANDOR** è una piattaforma ERP (Enterprise Resource Planning) verticale appositamente progettata per coprire l'intero ciclo operativo di un'impresa di pulizie e servizi integrati (facility management). Il software unisce in un unico ambiente le esigenze contabili dell'amministrazione e le necessità quotidiane dei responsabili di cantiere e dei lavoratori sul campo.

Con Kandor l'azienda ottiene:
- **Pianificazione automatizzata dei turni**: Trasformazione dei contratti cliente in calendarizzazioni settimanali o mensili senza inserimenti manuali ripetitivi.
- **Supporto ai contratti storici e in essere**: Generazione retroattiva dei turni passati con marcatura automatica delle ore in attesa di conferma.
- **Tracciamento presenze in tempo reale via Telegram**: Gli operatori registrano le ore o segnalano assenze tramite bot con bottoni interattivi direttamente dallo smartphone.
- **Ricerca Intelligente del Sostituto (Algoritmo "Jolly")**: Calcolo istantaneo delle distanze chilometriche GPS casa-cantiere per individuare i lavoratori idonei e disponibili in caso di emergenza.
- **Gestione Avvallo Assenze**: Workflow autorizzativo da parte dell'amministrazione con generazione automatica delle richieste di copertura verso i Responsabili Area.
- **Elaborazione Prospetto Paghe e Rettifiche Admin**: Report per lo studio di consulenza del lavoro con possibilità per l'amministrazione di rettificare giorni, ore e assenze prima della stampa o dell'esportazione.

### Requisiti Tecnici
- **Browser consigliati**: Google Chrome, Mozilla Firefox, Microsoft Edge o Apple Safari (versione aggiornata).
- **Connessione**: Connessione Internet attiva per l'utilizzo Cloud su Render, oppure rete locale in caso di installazione desktop locale.
- **Dispositivi Mobili**: L'app Telegram (gratuita per Android e iOS) installata sugli smartphone dei lavoratori per la messaggistica bidirezionale.

---

## 2. Accesso al Sistema e Sicurezza

### Accesso alla Piattaforma Cloud
L'indirizzo di riferimento per accedere al gestionale da qualsiasi postazione web è:
👉 **[https://kandor.onrender.com](https://kandor.onrender.com)**

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
- **Barra Superiore di Navigazione**: Mostra il logo Kandor, il nome dell'utente connesso, il link rapido al sito e il pulsante per il Logout.
- **Barra Laterale Sinistra (Operazioni Frequenti)**: Contiene i link rapidi alle funzionalità usate più spesso:
  - 🔄 **Trova Jolly**: Ricerca rapida sostituti per cantiere
  - 📊 **Riconciliazione**: Confronto ore contrattuali vs consuntivate
  - 📈 **Analisi Contratti**: Verifica redditività e contratti sotto soglia
  - 📥 **Gestione Dati**: Importazione ed esportazione file Excel/CSV
  - 📖 **Guide e Manuali**: Accesso alla documentazione completa
  - 💬 **Centro Messaggi**: Chat diretta bidirezionale via Telegram
  - ⚡ **Genera Turni**: Generazione automatica dei turni ordinari
  - 📄 **Vedi Report / Verifica Ore**: Report mensile ore e assenze con PDF
  - 💼 **Report Paghe**: Elaborazione prospetto paghe per il consulente del lavoro
- **Corpo Centrale**: Presenta la suddivisione modulare per **Risorse Anagrafiche** (Dipendenti, Clienti, Qualifiche, Mezzi, Squadre, Responsabili Area) e **Sezione Operativa** (Turni, Assenze, Time Tracking, Richieste Sostituzione).
- **Pannello Destro (Widget Dinamici)**: Contiene i box informativi ad aggiornamento automatico (Scadenze Veicoli, Compleanni in arrivo, Feed Telegram e Scadenze Contratti).

---

## 4. Gestione Anagrafica Dipendenti

### Scopo Operativo
Il modulo Dipendenti censisce tutti i lavoratori aziendali, raccogliendo le informazioni anagrafiche, le qualifiche professionali, i recapiti di contatto e la disponibilità ad effettuare sostituzioni d'emergenza.

### Percorso di Navigazione
👉 **Dashboard** → **Dipendenti** (oppure `/admin/core/dipendente/`)

### Guida Passo-Passo per l'Inserimento di un Nuovo Dipendente
1. Clicca su **Dipendenti** e poi sul pulsante in alto a destra **"+ Aggiungi Dipendente"**.
2. **Dati Anagrafici**:
   - Inserisci **Nome** e **Cognome**.
   - Inserisci il **Codice Fiscale** (16 caratteri alfanumerici).  
     *Automazione*: Se lasci il campo "Data di Nascita" vuoto, il sistema estrapolerà automaticamente la data di nascita corretta decodificando il Codice Fiscale.
   - Digita l'**Indirizzo di Residenza** completo (Via/Piazza, Numero Civico, CAP, Comune, Provincia).  
     *Automazione GPS*: Al salvataggio della scheda, Kandor invierà l'indirizzo al servizio di geocodifica integrato per calcolare la latitudine e la longitudine GPS. Tali coordinate sono indispensabili per calcolare i km di distanza quando si cercano sostituti per i cantieri.
3. **Contatti e Telegram**:
   - Inserisci il **Telefono** e l'**Email** del lavoratore.
   - **Telegram Chat ID**: Inserisci l'identificativo univoco dell'account Telegram del dipendente per abilitare l'invio e la ricezione di messaggi dal Bot aziendale.
4. **Competenze e Sostituzioni**:
   - Seleziona le **Qualifiche Possedute** nella lista a scelta multipla (es. Pulizie Industriali, Uso Monospazzola, Trattamento Cotto).
   - Se il lavoratore è disponibile a coprire i turni dei colleghi assenti, spunta la casella **"Disponibile come Sostituto"**.
5. **Stato Operativo**:
   - Imposta lo stato su **Attivo** per i lavoratori in servizio regolare. Gli altri stati (In Malattia, In Ferie, In Permesso, Legge 104, Licenziato/Inattivo) vengono aggiornati automaticamente dal sistema o dall'amministrazione.
6. Clicca **"Salva"** in basso a destra.

---

## 5. Gestione Anagrafica Clienti e Sedi

### Scopo Operativo
Anagrafica di tutti i clienti o cantieri aziendali presso i quali si svolgono i servizi di pulizia o manutenzione.

### Percorso di Navigazione
👉 **Dashboard** → **Clienti** (oppure `/admin/core/cliente/`)

### Descrizione dei Campi
- **Ragione Sociale**: Denominazione ufficiale dell'azienda cliente o del condominio/ente.
- **Partita IVA / Codice Fiscale**: Dati fiscali del cliente.
- **Indirizzo Sede / Cantiere**: Ubicazione esatta del cantiere. Come per i dipendenti, l'indirizzo viene geocodificato in coordinate GPS per calcolare le distanze dai lavoratori.
- **Nome Referente / Ruolo / Telefono**: Dati della persona di contatto in loco (es. Direttore di Cantiere, Amministratore di Condominio).
- **Data Nascita Referente**: Utilizzata dal widget della dashboard per segnalare i compleanni imminenti a scopo relazionale.
- **Ore Mensili Contratto**: Monte ore mensile pattuito nel contratto commerciale (utilizzato nel modulo di Riconciliazione Ore).
- **Importo Mensile Contratto (€)**: Corrispettivo economico mensile fatturato al cliente (utilizzato nel modulo di Analisi Economica Contratti).
- **Note / Istruzioni Cantiere**: Indicazioni operative specifiche (es. "Codice allarme 4321", "Chiavi presso la portineria").

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
- **Filtro nel "Trova Jolly"**: Quando si cerca un sostituto per un cantiere con qualifica speciale (es. "Lavori in Quota"), l'algoritmo esclude automaticamente i dipendenti che non possiedono quella specifica qualifica.

---

## 7. Gestione Parco Mezzi Aziendali

### Scopo Operativo
Monitoraggio e assegnazione dei veicoli commerciali e delle autovetture aziendali utilizzate dalle squadre per raggiungere i cantieri.

### Percorso di Navigazione
👉 **Dashboard** → **Mezzi Aziendali** (oppure `/admin/core/mezzo/`)

### Descrizione dei Campi
- **Modello Mezzo**: Descrizione del veicolo (es. *Fiat Doblo 1.3 Multijet*).
- **Targa**: Targa del veicolo (univoca nel sistema).
- **Stato Attuale**: Selezionabile tra *Disponibile*, *In Manutenzione*, *In Riparazione*, *Dismesso*.
- **Km Percorsi**: Chilometraggio aggiornato del veicolo.
- **Scadenza Polizza Assicurativa**: Data di scadenza dell'assicurazione.
- **Scadenza Bollo**: Data di scadenza della tassa di circolazione.

### Alert Scadenze Automatico
Il sistema controlla costantemente le date di scadenza di polizze e bolli. I veicoli con scadenze nei successivi 45 giorni o già scaduti vengono evidenziati nel widget **Scadenze Veicoli** nella Dashboard principale.

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
Dalla lista delle squadre, selezionando una squadra e scegliendo dal menu in basso **"💬 Invia Messaggio alla Squadra"**, l'amministrazione può inviare istantaneamente una comunicazione Telegram a tutti i componenti della squadra contemporaneamente.

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
3. Invia una notifica Telegram al Responsabile Area richiedendo la sua **autorizzazione/approvazione**.
4. Soltanto dopo che il RA ha confermato la richiesta, il bot invia la proposta di lavoro ai dipendenti sostituti.

---

## 10. Pianificazione Turni, Calendario e Composizione Retroattiva

### Scopo Operativo
Pianificazione delle attività lavorative quotidiane con visualizzazione a calendario e gestione avanzata sia per la programmazione futura sia per la regolarizzazione dei contratti storici già avviati nel passato.

### Percorso di Navigazione
👉 **Dashboard** → **Turni** oppure **Pianificazione Settimanale** (Calendario Interattivo)

### Caratteristiche del Calendario Interattivo
- **Vista Oraria Settimanale**: Mostra tutti i turni disposti nei vari giorni della settimana con l'indicazione del cliente, della squadra e degli orari previsti.
- **Filtri e Navigazione**: Pulsanti ← / → per spostarsi tra le settimane dell'anno e menu a tendina per filtrare per specifica squadra.
- **Badge di Stato delle Ore**:
  - 🟢 **Verde (`✅ Validate: Xh`)**: Le ore lavorate sono state verificate e approvate dall'amministrazione.
  - 🟡 **Giallo / Ambra (`⏳ Provvisorie: Xh`)**: Ore comunicate dal lavoratore via Telegram ma non ancora convalidate.
  - 🔴 **Rosso con punto esclamativo (`! In attesa di conferma`)**: Turno passato i cui consuntivi non sono ancora stati confermati.

### Generazione Automatica dei Turni
Dalla barra laterale, cliccando su **"⚡ Genera Turni"**, il sistema prende tutte le *Programmazioni Ricorrenti* attive dei clienti e genera automaticamente le assegnazioni per i **prossimi 7 giorni**, evitando la creazione di duplicati.

### Composizione Retroattiva per Contratti Storici e in Essere
Quando viene inserito un nuovo contratto o una nuova programmazione ricorrente che ha una **Data Inizio Contratto nel passato** (es. un contratto partito 2 mesi fa):
1. Al momento del salvataggio, Kandor calcola e compone in automatico tutti i turni giorno per giorno a partire dalla data d'inizio storica fino ad oggi.
2. I turni passati nascono nello stato **"In attesa di conferma delle ore lavorate"** (evidenziati con l'icona rossa **`!`** sul calendario).
3. Questo permette all'amministrazione di censire in qualsiasi momento i contratti già avviati nel passato e procedere alla verifica delle ore storiche.
4. **Protezione dello Storico**: Se successivamente si modifica la programmazione di un contratto, il sistema rigenera soltanto i turni da oggi in poi, lasciando intatti e protetti i turni passati già convalidati.

---

## 11. Programmazione Ricorrente Contratti

### Scopo Operativo
Definizione delle regole di ripetizione periodica delle pulizie e dei servizi per ciascun cliente.

### Percorso di Navigazione
👉 **Scheda Cliente** → Sezione **Programmazione Ricorrente** oppure dal menu Admin `/admin/core/programmazionericorrente/`

### Parametri della Programmazione
- **Tipo Ripetizione**:
  - **Settimanale**: Ripetizione in specifici giorni della settimana (es. tutti i Lunedì, Mercoledì e Venerdì).
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

## 13. Gestione Sostituti e Ricerca "Trova Jolly"

### Scopo Operativo
Procedura d'emergenza guidata per coprire rapidamente i turni rimasti scoperti a causa dell'assenza improvvisa di un operatore.

### Percorso di Navigazione
👉 **Calendario Turni** → Clicca sul turno scoperto → **"🔄 Trova Sostituto"**  
oppure dalla barra laterale **"Trova Jolly"** (`/admin/jolly-finder/`)

### Come Funziona l'Algoritmo "Jolly Finder" e la Selezione Ordinata
1. **Selezione del Turno Scoperto**: L'amministratore seleziona il turno o la richiesta di sostituzione generata dall'assenza.
2. **Filtro Automatico di Idoneità**: Kandor analizza l'intero organico aziendale ed esclude automaticamente:
   - I dipendenti non attivi o non abilitati come sostituti.
   - I lavoratori che risultano già in ferie, malattia o permesso in quella data.
   - I lavoratori che hanno già un altro turno di lavoro sovrapposto negli stessi orari.
   - I lavoratori privi della qualifica tecnica eventualmente richiesta dal cantiere.
3. **Calcolo Geometrico della Distanza GPS**: L'algoritmo calcola la distanza stradale esatta (in km) tra l'indirizzo di residenza di ciascun lavoratore disponibile e l'indirizzo del cantiere da coprire.
4. **Finestra di Selezione Ordinata dei Sostituti**: Prima di inviare le notifiche Telegram o gli avvisi, il sistema apre una finestra interattiva pop-up con l'elenco dei sostituti idonei ordinati per distanza e qualifiche.
5. **Ordinamento di Preferenza**: L'amministrazione può spuntare i candidati desiderati definendo **l'ordine esatto di selezione/invio** (es. 1° scelta, 2° scelta, 3° scelta).
6. **Inoltro Notifiche Sequenziale**: Confermata la selezione, il sistema invia la notifica prioritariamente ai candidati scelti nell'ordine stabilito.

![Schermata Gestione Richieste Sostituzione](screenshots/02_gestione_sostituzioni.png)

### Risposta del Sostituto via Telegram
Dopo l'invio della notifica, il sostituto riceve sul suo telefono un messaggio Telegram completo di:
- Nome e indirizzo esatto del cantiere.
- Data e orari del turno.
- Distanza da casa sua in km.
- Nomi e numeri di telefono dei compagni di squadra presenti.
- Bottoni interattivi **"✅ Accetto"** e **"❌ Rifiuto"**.

Il sostituto ha tempo per accettare. Qualora rifiuti o non risponda, il sistema notifica l'amministrazione e procede automaticamente con la notifica al successivo sostituto selezionato in ordine di priorità.

---

## 14. Registrazione Ore (Time Tracking) e Validazione 1-Click

### Scopo Operativo
Consuntivazione delle ore di lavoro effettivamente svolte dagli operatori sul campo e relativo processo di approvazione contabile.

### Modalità di Registrazione delle Ore
Le ore possono entrare nel sistema attraverso due canali:
1. **Via Telegram (da parte del lavoratore)**: A fine giornata l'operatore seleziona il turno dal bot Telegram e digita le ore svolte (es. `8` o `7.5`).
2. **Inserimento Manuale Admin**: Dall'interfaccia di gestione `Time Tracking` o direttamente dal Calendario dei turni.

### Procedura di Validazione Rapida 1-Click dal Calendario
Per velocizzare il lavoro quotidiano dell'amministrazione:
1. Apri la vista **Pianificazione Settimanale** nella Dashboard.
2. I turni per i quali il lavoratore ha inserito le ore via Telegram presentano il badge ambra **`⏳ Provvisorie: Xh`** e il pulsante con l'icona della spunta `✓` evidenziato in colore arancione.
3. Cliccando direttamente sull'icona `✓`, le ore vengono **convalidate al volo** con un solo click e il badge diventa verde **`✅ Validate: Xh`**.
4. In alternativa, cliccando sul turno si apre la scheda di dettaglio da cui è possibile rettificare le ore e cliccare su **"✔ Salva e valida"**.

---

## 15. Verifica Ore Mensili e Riconciliazione Storica

### Scopo Operativo
Pannello di controllo per la verifica globale delle ore lavorate, contrattuali e non validate relative a qualsiasi mese presente o passato.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Vedi Report** (oppure `/verifica-ore/`)

### Utilizzo del Report per la Verifica dei Mesi Precedenti
1. Dai menu a tendina in alto, seleziona il **Mese** e l'**Anno** da analizzare (es. *Maggio 2026*).
2. Clicca sul pulsante **"Aggiorna"**.
3. Il sistema rielabora istantaneamente tutti i dati del mese selezionato presentando tre tabelle riassuntive:
   - **Tabella 1: Riepilogo per Cliente**: Confronto tra ore di contratto previste, ore effettivamente lavorate e validate, differenza in ore e valore economico.
   - **Tabella 2: Riepilogo per Squadra e Dipendente**: Dettaglio delle ore svolte da ogni singolo lavoratore suddivise per squadra.
   - **Tabella 3: Riepilogo Assenze del Mese**: Conteggio dettagliato per lavoratore dei giorni di assenza usufruiti nel mese (Malattia, Ferie, Permessi, Legge 104). Cliccando sul nome del dipendente si espande il dettaglio analitico di ciascun periodo di assenza.
4. **Stampa PDF**: Cliccando su **"📄 Scarica PDF"** viene generato il documento ufficiale stampabile con il riepilogo contabile completo.

---

## 16. Report Paghe, Buste Paga e Rettifiche Amministrative

### Scopo Operativo
Modulo dedicato all'elaborazione del prospetto retributivo mensile da trasmettere allo Studio del Consulente del Lavoro per la stampa delle buste paga, integrato con la possibilità di effettuare rettifiche amministrative.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Report Paghe** (oppure `/admin/report-paghe/`)

### Funzionalità di Rettifica Amministrativa ("✏️ Rettifica")
Qualora vi siano stati errori nella timbratura delle ore via Telegram, omissioni o accordi correttivi dell'ultimo minuto:
1. Nella tabella del Report Paghe, individua la riga del dipendente interessato (es. *AVOGADRO CLARA*).
2. Nella colonna **Azione Admin** sulla destra, clicca sul pulsante **`✏️ Rettifica`**.
3. Si aprirà un modale interattivo denominato **"Rettifica Cedolino Paghe - [Nome Dipendente]"**.
4. **Campi di Override Modificabili**:
   - **Giorni Lavorati Override**: Inserisci il numero corretto di giornate lavorate nel mese.
   - **Ore Totali Override**: Inserisci le ore complessive rettificate.
   - **Ore Validate Override**: Correggi il totale delle ore validate.
   - **Giorni Ferie / Permessi / Malattia Override**: Rettifica i giorni di assenza del mese.
   - **Note Rettifica (Obbligatorio)**: Inserisci la motivazione amministrativa della modifica (es. *"Corrette ore per mancata timbratura cantiere c/o Hotel Roma approvata dal responsabile"*).
5. Clicca su **"💾 Salva Rettifica"**.
6. **Effetto Immediato**: La riga del dipendente mostrerà il badge **`✏️ Rettificato`**, la tabella aggiornerà istantaneamente i totali generali ed i KPI del mese e l'annotazione comparirà sia nel **PDF stampabile per il Consulente** sia nell'**Esportazione Excel/CSV**.
7. Per annullare una rettifica e ripristinare i valori originali calcolati dal sistema, basta riaprire il modale e cliccare sul pulsante rosso **"🗑️ Elimina Rettifica"**.

![Schermata Report Paghe e Modale Rettifica Cedolino](screenshots/04_report_paghe.png)

---

## 17. Gestione Assenze, Avvallo e Sostituzioni Automatiche

### Scopo Operativo
Censimento delle assenze dei lavoratori con workflow autorizzativo dell'amministrazione ed automazione della ricerca sostituti.

### Percorso di Navigazione
👉 **Dashboard** → **Assenze** (oppure `/admin/core/assenza/`)

### Workflow con Avvallo Amministrativo e Avvio Automatico Sostituzioni
1. **Segnalazione Assenza**: L'assenza per malattia, ferie o permesso viene inviata dall'operatore via Telegram o registrata dall'amministrazione. Inizialmente nasce nello stato **"In Attesa Avvallo Amministrazione"**.
2. **Valutazione e Avvallo dell'Amministrazione**: L'amministratore apre la scheda dell'assenza, verifica i certificati/motivazioni e clicca su **"Approvata (Avvallata)"** o **"Approva e Avvia Sostituzione"**.
3. **Avvio Automatico Procedura di Sostituzione**: Subito dopo l'avvallo dell'amministrazione, Kandor esamina tutti i turni in cui era programmato l'assente e attiva in automatico la procedura di sostituzione.
4. **Apertura Finestra Selezione Sostituti**: Prima di inviare le notifiche, il sistema visualizza la finestra pop-up con i candidati disponibili. L'amministrazione seleziona i sostituti desiderati e imposta l'ordine di priorità (1°, 2°, 3° scelta) prima dell'invio automatico delle notifiche via Telegram.

![Schermata Gestione Assenze e Avvallo Amministrazione](screenshots/05_gestione_assenze.png)

---

## 18. Segnalazioni dagli Operatori

### Scopo Operativo
Gestione delle comunicazioni di servizio, anomalie o guasti inviati dai lavoratori dai cantieri.

### Percorso di Navigazione
👉 **Dashboard** → **Segnalazioni** (oppure `/admin/core/segnalazione/`)

### Gestione delle Segnalazioni
- Quando un lavoratore scrive al bot Telegram una segnalazione (o invia una fotografia di un danno o di una macchina guasta), la segnalazione compare in tempo reale nel pannello Admin.
- L'amministratore può prendere in carico la segnalazione, inserire le **Note Amministrazione** e spuntare la casella **"Risolto"** una volta completata l'assistenza.

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

### Report di Reditività
Il sistema confronta l'importo mensile fatturato al cliente con la somma del costo orario dei lavoratori impiegati sul cantiere:
- Calcola il **Costo Orario Effettivo per Cantiere**.
- Segnala con alert visivi i contratti che generano una perdita o un margine inferiore alla soglia minima impostata.
- Permette di esportare il **Report Economico in PDF** per le riunioni di direzione.

---

## 21. Integrazione Bot Telegram per Lavoratori

### Scopo Operativo
Fornire ai lavoratori uno strumento semplice ed immediato sul proprio smartphone per interagire con l'azienda senza installare app complesse.

### Nome e Contatto del Bot
- Nome Bot: **Kandor Assistente** (`@kandor_gestionale_bot`)
- Link di avvio: **[https://t.me/kandor_gestionale_bot](https://t.me/kandor_gestionale_bot)**

### Bottoni del Menu Principale Telegram
All'invio di qualsiasi testo, il bot risponde mostrando i bottoni guida:
- ⏱ **Registra Ore**: Mostra i turni della giornata e permette di digitare le ore svolte.
- 📋 **Turni Non Compilati**: Elenca i turni degli ultimi 7 giorni ancora privi di consuntivo.
- 🤒 **Malattia** / 🏖️ **Ferie** / 📝 **Permesso**: Registrazione immediata dello stato di assenza per la giornata.
- ⚠️ **Segnalazione**: Invio di note o fotografie direttamente all'ufficio.
- 📖 **Guida**: Apertura del manuale istruzioni per il lavoratore.

---

## 22. Messaggi Programmati e Comunicazioni di Massa

### Scopo Operativo
Pianificazione dell'invio differito di comunicazioni o circolari aziendali via Telegram.

### Percorso di Navigazione
👉 **Dashboard** → **Messaggi Programmabili** (oppure `/admin/core/messaggioprogrammato/`)

### Configurazione Invio
1. Inserisci il **Titolo** ed il **Testo del Messaggio**.
2. Imposta la **Data e Ora di Invio** programmata.
3. Seleziona i **Destinatari Specifici** oppure spunta la casella **"Invia a TUTTI"** per raggiungere l'intero organico attivo.
4. Il sistema eseguirà l'invio automatico all'orario stabilito.

---

## 23. Centro Messaggi e Chat Bidirezionale Telegram

### Scopo Operativo
Console di messaggistica bidirezionale in tempo reale per conversare direttamente con i dipendenti via Telegram senza uscire dall'interfaccia di Kandor.

### Percorso di Navigazione
👉 **Operazioni Frequenti** → **Centro Messaggi** (oppure `/chat-simulator/`)

### Funzionalità della Chat
- **Lista Conversazioni**: Elenco a sinistra dei lavoratori con badge rosso per i messaggi non letti.
- **Visualizzazione Foto**: Possibilità di ingrandire e scaricare le foto inviate dagli operatori dai cantieri.
- **Invio Broadcast / Per Squadra**: Pulsanti dedicati per inviare comunicazioni istantanee ad una specifica squadra o a tutti i lavoratori.

---

## 24. Gestione Dati, Import/Export Excel e Backup

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

## 25. Widget Dashboard e Monitoraggio Scadenze

Il pannello informativo destro della Dashboard include widget ad aggiornamento automatico:

1. 🚗 **Scadenze Veicoli**:
   - Visualizza i veicoli con assicurazione o bollo in scadenza nei successivi 45 giorni (colore arancione) o già scaduti (colore rosso).
2. 🎂 **Compleanni in Arrivo**:
   - Mostra i compleanni dei dipendenti e dei referenti clienti nei successivi 20 giorni.
3. 📅 **Pianificazione Settimanale**:
   - Calendario sintetico dei turni con stato delle ore e navigazione rapida.
4. 📱 **Feed Telegram**:
   - Flusso in tempo reale degli ultimi messaggi, timbrature e segnalazioni ricevute dagli operatori.

---

## 26. FAQ, Risoluzione Problemi e Domande Frequenti

### ❓ Il primo caricamento del sito Cloud è lento. È un malfunzionamento?
**Risposta**: No. Su Render (piano gratuito) il server va in standby dopo 15 minuti di inattività per risparmiare risorse. Il riavvio richiede circa 45-60 secondi, trascorsi i quali la navigazione torna ad essere velocissima.

### ❓ Un dipendente dice di non ricevere i messaggi dal Bot Telegram. Cosa verificare?
**Risposta**:
1. Verifica che nella scheda del dipendente sia stato inserito il **Telegram Chat ID** corretto.
2. Assicurati che il dipendente abbia cliccato su **"AVVIA"** / **"/start"** all'interno del Bot `@kandor_gestionale_bot`.

### ❓ Come si recupera il Telegram Chat ID di un dipendente?
**Risposta**: Fai scrivere un messaggio qualsiasi al lavoratore verso il bot `@kandor_gestionale_bot`. Se il suo ID non è ancora registrato, il bot gli risponderà comunicandogli il suo numero univoco (es. `123456789`). L'amministratore dovrà semplicemente copiare quel numero nella scheda del dipendente.

### ❓ Perché nel report delle buste paga le ore non corrispondono con quelle che dichiara il dipendente?
**Risposta**: Il report contabile contabilizza soltanto le **ore convalidate** (badge verde). Se il dipendente ha inserito le ore ma l'amministrazione non le ha ancora convalidate (badge ambra ⏳), le ore rimarranno in stato provvisorio. Inoltre, l'amministrazione può intervenire in qualsiasi momento tramite il pulsante **`✏️ Rettifica`** per impostare gli override correttivi.

### ❓ Cosa succede se inserisco un dato errato o incompleto in un form? Il sistema mi disconnette?
**Risposta**: No. In caso di inserimento di dati errati o non validi (es. Codice Fiscale di lunghezza errata, targa duplicata o date incongruenti), il sistema evidenzia l'errore in un banner rosso e segnala il campo specifico. L'utente rimane all'interno della pagina con le informazioni già compilate conservate, senza venire disconnesso o reindirizzato a schermate di errore generico (500).

### ❓ Come funziona la selezione ordinata dei sostituti all'approvazione dell'assenza?
**Risposta**: All'approvazione dell'assenza (malattia, ferie, permesso) parte in automatico la procedura di sostituzione. Prima dell'invio dei messaggi, si apre la finestra pop-up con l'elenco dei sostituti idonei trovati dal sistema. L'amministrazione può selezionare le persone desiderate e definirne l'ordine numerico di invio dell'avviso (1°, 2°, 3° scelta), così che le notifiche vengano inoltrate secondo le preferenze stabilite.

---

> **KANDOR ERP** — Gestionale Operativo per Imprese di Servizi  
> *Sviluppato da Studio Serra — © 2026*
