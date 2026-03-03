# 📘 KANDOR — Manuale d'Uso Completo

> **Versione**: 1.0  
> **Ultimo aggiornamento**: Marzo 2026  
> **URL**: [kandor.onrender.com](https://kandor.onrender.com)

---

## Sommario

1. [Introduzione](#1-introduzione)
2. [Accesso al Sistema](#2-accesso-al-sistema)
3. [Dashboard Principale](#3-dashboard-principale)
4. [Gestione Dipendenti](#4-gestione-dipendenti)
5. [Gestione Clienti](#5-gestione-clienti)
6. [Gestione Qualifiche](#6-gestione-qualifiche)
7. [Gestione Mezzi Aziendali](#7-gestione-mezzi-aziendali)
8. [Gestione Squadre](#8-gestione-squadre)
9. [Pianificazione Turni](#9-pianificazione-turni)
10. [Programmazione Ricorrente](#10-programmazione-ricorrente)
11. [Richieste Straordinarie](#11-richieste-straordinarie)
12. [Trova Jolly](#12-trova-jolly)
13. [Registrazione Ore (Time Tracking)](#13-registrazione-ore-time-tracking)
14. [Gestione Assenze](#14-gestione-assenze)
15. [Segnalazioni](#15-segnalazioni)
16. [Riconciliazione Ore](#16-riconciliazione-ore)
17. [Integrazione Telegram](#17-integrazione-telegram)
18. [Messaggi Programmati](#18-messaggi-programmati)
19. [Simulatore Chat](#19-simulatore-chat)
20. [Gestione Dati (Import/Export)](#20-gestione-dati-importexport)
21. [Backup e Ripristino](#21-backup-e-ripristino)
22. [Widget Dashboard](#22-widget-dashboard)
23. [FAQ e Risoluzione Problemi](#23-faq-e-risoluzione-problemi)

---

## 1. Introduzione

**KANDOR** è un sistema ERP (Enterprise Resource Planning) progettato per la gestione operativa di imprese di servizi, in particolare aziende di pulizie e facility management. Il sistema permette di:

- **Gestire dipendenti** con dati anagrafici, qualifiche e stato
- **Gestire clienti** con indirizzi e programmazione lavori
- **Pianificare turni** automaticamente basandosi su programmazioni ricorrenti
- **Tracciare le ore lavorate** in tempo reale, anche via Telegram
- **Gestire assenze** (malattia, ferie, permessi)
- **Trovare sostituti** (Jolly) in caso di emergenza
- **Riconciliare le ore** previste vs lavorate per ogni cliente
- **Comunicare con i dipendenti** tramite Telegram

### Requisiti di Sistema

- Un browser web moderno (Chrome, Firefox, Edge, Safari)
- Connessione Internet
- Per l'integrazione Telegram: l'app Telegram sul telefono del dipendente

---

## 2. Accesso al Sistema

### URL di Accesso

Apri il browser e vai a: **[kandor.onrender.com](https://kandor.onrender.com)**

Il sistema reindirizzerà automaticamente al pannello di amministrazione.

### Login

1. Inserisci **Nome utente** e **Password**
2. Clicca **"Accedi"**

> ⚠️ **Nota**: L'istanza gratuita di Render si "addormenta" dopo 15 minuti di inattività. Il primo accesso potrebbe richiedere fino a 50 secondi.

### Cambio Password

1. Dopo il login, clicca sul tuo nome utente in alto a destra
2. Seleziona **"Cambia password"**
3. Inserisci la vecchia password e la nuova (2 volte)
4. Clicca **"Cambia la mia password"**

---

## 3. Dashboard Principale

La homepage del pannello mostra la scritta **"Benvenuto in Kandor"** e si divide in sezioni:

### Barra Laterale

La barra laterale contiene i link rapidi alle funzioni principali:

| Link | Funzione |
|------|----------|
| **Trova Jolly** | Cerca sostituti disponibili |
| **Riconciliazione** | Confronta ore previste vs lavorate |
| **Gestione Dati** | Import/Export dati Excel |
| **Chat Simulator** | Testa messaggi Telegram |
| **Genera Turni** | Genera turni automatici per 7 giorni |
| **Manuale** | Apri questo manuale |

### Sezione Risorse

Accesso a: Clienti, Dipendenti, Mezzi, Qualifiche, Squadre, Messaggi Programmati

### Sezione Operativa

Accesso a: Assegnazioni Turno, Assenze, Registrazioni Ore, Turni

### Widget (Pannello Destro)

Vedi la sezione [Widget Dashboard](#22-widget-dashboard) per i dettagli.

---

## 4. Gestione Dipendenti

### Accesso
**Dashboard** → **Dipendenti** → **Aggiungi Dipendente** o clicca su un dipendente esistente

### Campi Disponibili

#### Dati Anagrafici
| Campo | Descrizione | Obbligatorio |
|-------|-------------|:---:|
| **Nome** | Nome del dipendente | ✅ |
| **Cognome** | Cognome del dipendente | ✅ |
| **Codice Fiscale** | CF univoco, 16 caratteri | ✅ |
| **Data di Nascita** | Calcolata automaticamente dal CF se non inserita | ❌ |
| **Indirizzo Residenza** | Indirizzo completo (geocodificato automaticamente) | ✅ |
| **Email** | Indirizzo email | ❌ |
| **Telefono** | Numero di telefono | ❌ |

#### Dati Contrattuali
| Campo | Descrizione |
|-------|-------------|
| **Categoria Protetta** | Checkbox, indica se è categoria protetta |
| **File Contratto** | Upload del file contratto (PDF, ecc.) |
| **Qualifiche Possedute** | Selezione multipla delle qualifiche |

#### Integrazione Telegram
| Campo | Descrizione |
|-------|-------------|
| **Telegram Chat ID** | ID univoco della chat Telegram del dipendente |

#### Stato
| Stato | Significato |
|-------|-------------|
| **Attivo** | In servizio regolare |
| **In Malattia** | Assente per malattia |
| **In Ferie** | Assente per ferie |
| **In Permesso** | Assente per permesso |
| **Legge 104** | Assente per legge 104 |
| **Licenziato/Inattivo** | Non più in servizio |

### Funzionalità Speciali

- **Geocodifica automatica**: Quando inserisci l'indirizzo, il sistema calcola automaticamente le coordinate GPS (latitudine/longitudine). Queste vengono usate per il calcolo della distanza nel "Trova Jolly".
- **Data di nascita dal CF**: Se non inserisci la data di nascita, il sistema la estrarrà automaticamente dal codice fiscale.

### Ricerca e Filtri

- **Barra di ricerca**: Cerca per cognome, nome, codice fiscale o Telegram Chat ID
- **Filtri laterali**: Filtra per stato (Attivo, In Malattia, ecc.) e per qualifiche

### Azione: Invia Messaggio Telegram

1. Seleziona uno o più dipendenti tramite le checkbox
2. Dal menu **"Azione"** in basso, scegli **"💬 Invia Messaggio Telegram"**
3. Clicca **"Esegui"**
4. Scrivi il messaggio nella pagina intermedia
5. Clicca **"Invia"**

> Il messaggio verrà inviato via Telegram a tutti i dipendenti selezionati che hanno un Chat ID configurato.

---

## 5. Gestione Clienti

### Accesso
**Dashboard** → **Clienti**

### Campi Disponibili

| Campo | Descrizione | Obbligatorio |
|-------|-------------|:---:|
| **Ragione Sociale** | Nome dell'azienda cliente | ✅ |
| **Partita IVA** | P.IVA univoca (max 20 caratteri) | ❌ |
| **Codice Fiscale** | CF del cliente | ❌ |
| **Indirizzo Sede** | Indirizzo completo (geocodificato autom.) | ✅ |
| **Nome Titolare/Referente** | Nome della persona di riferimento | ❌ |
| **Ruolo** | Ruolo del referente | ❌ |
| **Data Nascita Referente** | Per auguri compleanno (widget dashboard) | ❌ |
| **Ore Mensili Contratto** | Ore che il contratto prevede al mese | ❌ |
| **Note Mansioni** | Descrizione delle mansioni richieste | ❌ |

### Sezioni Inline (nella scheda cliente)

Ogni cliente ha due sezioni aggiuntive direttamente nella scheda:

#### Programmazione Ricorrente
Permette di definire gli appuntamenti fissi (settimanali o mensili) per quel cliente. Vedi sezione [Programmazione Ricorrente](#10-programmazione-ricorrente).

#### Richieste Straordinarie
Permette di inserire lavori extra non ricorrenti. Vedi sezione [Richieste Straordinarie](#11-richieste-straordinarie).

---

## 6. Gestione Qualifiche

### Accesso
**Dashboard** → **Qualifiche**

Le qualifiche definiscono le competenze che i dipendenti possono avere (es. "Pulizie industriali", "Giardinaggio", "Sanificazione").

| Campo | Descrizione |
|-------|-------------|
| **Nome** | Nome della qualifica |
| **Descrizione** | Descrizione dettagliata (opzionale) |

Le qualifiche vengono assegnate ai dipendenti e possono essere richieste nelle programmazioni ricorrenti. Servono anche nel "Trova Jolly" per filtrare i candidati.

---

## 7. Gestione Mezzi Aziendali

### Accesso
**Dashboard** → **Mezzi Aziendali**

### Campi Disponibili

| Campo | Descrizione |
|-------|-------------|
| **Modello Mezzo** | Modello del veicolo (es. "Fiat Ducato") |
| **Targa** | Targa univoca del veicolo |
| **Stato Attuale** | Disponibile / In Manutenzione / In Riparazione |
| **Km Percorsi** | Chilometraggio attuale |
| **Scadenza Polizza** | Data scadenza assicurazione |
| **Scadenza Bollo** | Data scadenza bollo |

### Alert Scadenze

Il sistema controlla automaticamente le scadenze e mostra un **widget nella dashboard** per i mezzi con scadenze nei prossimi 45 giorni o già scadute (vedi [Widget Dashboard](#22-widget-dashboard)).

---

## 8. Gestione Squadre

### Accesso
**Dashboard** → **Squadre**

Le squadre raggruppano dipendenti sotto un caposquadra e vengono assegnate ai turni.

| Campo | Descrizione |
|-------|-------------|
| **Nome** | Nome della squadra (es. "Squadra Alpha") |
| **Caposquadra** | Dipendente responsabile |
| **Componenti** | Lista dei dipendenti che fanno parte della squadra |

### Azione: Invia Messaggio alla Squadra

1. Seleziona una o più squadre
2. Scegli **"💬 Invia Messaggio alla Squadra"**
3. Scrivi il messaggio
4. Il messaggio verrà inviato a **tutti i membri** delle squadre selezionate che hanno Telegram configurato

---

## 9. Pianificazione Turni

### Accesso
**Dashboard** → **Turni**

Un **Turno** rappresenta un giorno di lavoro per una squadra specifica.

| Campo | Descrizione |
|-------|-------------|
| **Data Turno** | Data del turno |
| **Squadra Assegnata** | La squadra che lavora |
| **Mezzo Utilizzato** | Il veicolo assegnato (opzionale) |

#### Assegnazioni Turno (Inline)
All'interno di ogni turno, si definiscono le **Assegnazioni** — cioè "la squadra va dal cliente X dalle Y alle Z":

| Campo | Descrizione |
|-------|-------------|
| **Cliente** | Il cliente da servire |
| **Orario Inizio Previsto** | Ora di inizio |
| **Orario Fine Previsto** | Ora di fine |
| **Mansione Svolta** | Descrizione del lavoro |
| **Programmazione Feriale** | Link alla programmazione ricorrente (opzionale) |
| **Richiesta Straordinaria** | Link alla richiesta extra (opzionale) |

### Generazione Automatica Turni

Dalla dashboard, clicca **"Genera Turni"** per creare automaticamente le assegnazioni per i **prossimi 7 giorni** basandosi sulle programmazioni ricorrenti.

Il sistema:
1. Analizza tutte le programmazioni con squadra/mezzo abituale assegnati
2. Per ogni giorno, verifica quali programmazioni corrispondono (per giorno della settimana o del mese)
3. Crea automaticamente Turno + Assegnazione Turno
4. Evita duplicati se i turni esistono già

---

## 10. Programmazione Ricorrente

Accessibile dalla **scheda del Cliente** (sezione inline).

La programmazione ricorrente definisce i **lavori fissi** presso un cliente.

| Campo | Descrizione |
|-------|-------------|
| **Tipo Ripetizione** | Settimanale o Mensile |
| **Giorno della Settimana** | Per ripetizione settimanale (Lunedì-Domenica) |
| **Giorno del Mese** | Per ripetizione mensile (1-31) |
| **Ora Inizio** | Orario di inizio (formato HH:MM, es. 06:30) |
| **Durata** | Durata in ore (es. 2.5 = 2 ore e 30 minuti) |
| **Ora Fine** | ⚡ Calcolata automaticamente da Ora Inizio + Durata |
| **Orario Flessibile** | Se attivo, gli orari sono indicativi |
| **Mansione/Qualifica** | Qualifica richiesta per questo lavoro |
| **Squadra Abituale** | La squadra che normalmente svolge il lavoro |
| **Mezzo Abituale** | Il veicolo normalmente utilizzato |

### Validazioni Automatiche

- Il sistema verifica che non ci siano **sovrapposizioni orarie** per la stessa squadra o lo stesso mezzo nello stesso giorno/ora.
- Se rileva un conflitto, mostra un errore con i dettagli dello scontro.

---

## 11. Richieste Straordinarie

Accessibili dalla **scheda del Cliente** (sezione inline).

| Campo | Descrizione |
|-------|-------------|
| **Data Inizio** | Data del lavoro straordinario |
| **Data Fine** | Data di fine (se più giorni) |
| **Ora Inizio** | Orario di inizio |
| **Ora Fine** | Orario di fine |
| **Descrizione Attività** | Cosa bisogna fare |
| **Completata** | Checkbox per segnare come completata |

---

## 12. Trova Jolly

### Accesso
**Dashboard** → **Trova Jolly** oppure URL: `/find-jolly/`

Questa funzione trova **dipendenti sostituti** disponibili per una copertura improvvisa.

### Come Usarlo

1. Seleziona il **Cliente** dove serve il sostituto
2. (Opzionale) Seleziona la **Qualifica richiesta**
3. Inserisci la **Data** del lavoro
4. Inserisci gli **orari** (inizio e fine)
5. Clicca **"Cerca"**

### Criteri di Filtro

Il sistema filtra automaticamente e mostra solo dipendenti che:

1. ✅ Sono in stato **ATTIVO**
2. ✅ **NON** sono in ferie/malattia/permesso in quella data
3. ✅ **NON** sono già impegnati in un turno che si sovrappone all'orario richiesto
4. ✅ Possiedono la **qualifica** richiesta (se specificata)

### Ranking dei Risultati

I risultati sono ordinati per **distanza geografica** (dal più vicino al più lontano) tra la residenza del dipendente e la sede del cliente. La distanza viene calcolata in chilometri usando le coordinate GPS.

---

## 13. Registrazione Ore (Time Tracking)

### Accesso
**Dashboard** → **Time Tracking** oppure via **Telegram**

| Campo | Descrizione |
|-------|-------------|
| **Dipendente** | Chi ha lavorato |
| **Assegnazione** | L'assegnazione turno collegata |
| **Check-in** | Data/ora di inizio lavoro |
| **Check-out** | Data/ora di fine lavoro |
| **Note** | Note aggiuntive |
| **Origine** | Manuale, Telegram o WhatsApp |
| **Validato** | Checkbox per conferma amministrativa |

La **durata in ore** viene calcolata automaticamente dalla differenza tra check-out e check-in.

### Registrazione via Telegram

I dipendenti possono inviare le ore direttamente dal telefono via Telegram (vedi sezione [Integrazione Telegram](#17-integrazione-telegram)).

---

## 14. Gestione Assenze

### Accesso
**Dashboard** → **Assenze**

| Campo | Descrizione |
|-------|-------------|
| **Dipendente** | Chi è assente |
| **Tipo** | Ferie / Malattia / Permesso / Legge 104 / Altro |
| **Data Inizio** | Primo giorno di assenza |
| **Data Fine** | Ultimo giorno di assenza |
| **Note** | Note aggiuntive |
| **Origine** | Manuale o Telegram |
| **Processato** | Checkbox per conferma amministrativa |

### Filtri

- Per **tipo** di assenza
- Per **data inizio**
- Ricerca per **cognome** del dipendente

### Registrazione via Telegram

I dipendenti possono comunicare assenze via Telegram scrivendo semplicemente "Malattia", "Ferie" o "Permesso" al bot.

---

## 15. Segnalazioni

Le segnalazioni vengono inviate dai dipendenti tramite Telegram (comando "Segnalazione: testo...").

| Campo | Descrizione |
|-------|-------------|
| **Dipendente** | Chi ha fatto la segnalazione |
| **Testo** | Contenuto della segnalazione |
| **Data Inserimento** | Quando è stata inserita |
| **Risolto** | Checkbox per chiudere la segnalazione |
| **Note Amministrazione** | Risposta o commento dell'amministratore |

---

## 16. Riconciliazione Ore

### Accesso
**Dashboard** → **Riconciliazione** oppure URL: `/reconciliation/`

Questa pagina confronta le **ore contrattuali** di ogni cliente con le **ore effettivamente lavorate** in un dato mese.

### Come Usarlo

1. Seleziona il **mese** e l'**anno** dai menu a tendina
2. Il sistema mostra la tabella per tutti i clienti

### Tabella Risultati

| Colonna | Descrizione |
|---------|-------------|
| **Cliente** | Ragione sociale |
| **Ore Previste** | Ore mensili da contratto |
| **Ore Reali** | Ore effettivamente tracciate |
| **Differenza** | Ore reali − Ore previste |
| **Stato** | Indicatore colorato |

### Indicatori di Stato

| Colore | Significato |
|--------|-------------|
| 🟢 **Verde (OK)** | Differenza entro ±5 ore |
| 🟠 **Arancione (WARNING)** | Più di +5 ore (straordinari non previsti) |
| 🔴 **Rosso (ALARM)** | Più di −5 ore (lavoro non svolto o fatturato mancante) |

---

## 17. Integrazione Telegram

### Configurazione Iniziale

1. Ogni dipendente deve avviare una conversazione con il bot Telegram dell'azienda
2. Il bot comunicherà il proprio **Chat ID** al dipendente
3. L'amministratore inserisce il Chat ID nella scheda del dipendente (campo "Telegram Chat ID")

### Comandi Disponibili per i Dipendenti

| Messaggio | Azione |
|-----------|--------|
| `Hotel Roma 8` | Registra 8 ore di lavoro per il cliente "Hotel Roma" |
| `Pulizie Centro 4.5` | Registra 4.5 ore per "Pulizie Centro" |
| `Roma 6:30` | Registra 6 ore e 30 minuti (formato HH:MM) |
| `Malattia` | Registra assenza per malattia (giorno corrente) |
| `Ferie` | Registra assenza per ferie (giorno corrente) |
| `Permesso` | Registra assenza per permesso (giorno corrente) |
| `Segnalazione testo...` | Invia una segnalazione all'amministrazione |

### Come Funziona il Riconoscimento

1. **Dipendente**: Il bot identifica il dipendente tramite il Telegram Chat ID
2. **Cliente**: Il bot cerca tra tutti i clienti il nome più simile a quello scritto (ricerca fuzzy)
3. **Ore**: Il bot legge il numero alla fine del messaggio

### Risposte del Bot

- ✅ `Salvato! 8h per Hotel Roma.` — Ore registrate con successo
- 🤒 `Mi dispiace che stai male! Ho registrato la MALATTIA per oggi.`
- 🏖️ `Ferie registrate per oggi.`
- 📝 `Ho preso nota della tua segnalazione.`
- ❌ `Non ho trovato nessun cliente simile a '...'` — Nome non riconosciuto
- 🚫 `Non ti conosco! Il tuo ID Telegram è: ...` — Chat ID non registrato

### Feed Telegram nella Dashboard

Le ultime registrazioni via Telegram vengono mostrate in un widget dedicato nella dashboard (vedi [Widget Dashboard](#22-widget-dashboard)).

---

## 18. Messaggi Programmati

### Accesso
**Dashboard** → **Messaggi Programmabili**

Permette di programmare l'invio di messaggi Telegram ai dipendenti.

| Campo | Descrizione |
|-------|-------------|
| **Titolo** | Titolo/descrizione del messaggio |
| **Testo** | Contenuto del messaggio da inviare |
| **Data e Ora di Invio** | Quando inviare il messaggio |
| **Destinatari Specifici** | Selezione multipla dei dipendenti |
| **Invia a TUTTI** | Se attivo, invia a tutti i dipendenti attivi |
| **Inviato** | Stato dell'invio (automatico) |

---

## 19. Simulatore Chat

### Accesso
**Dashboard** → **Chat Simulator** oppure URL: `/chat-simulator/`

Il simulatore permette di **inviare messaggi Telegram direttamente** ai dipendenti dalla piattaforma web.

### Come Usarlo

1. Seleziona un **dipendente** dal menu a tendina (mostra solo dipendenti attivi)
2. Scrivi il **messaggio** nel campo di testo
3. Clicca **"Invia"**

Il messaggio verrà inviato tramite il bot Telegram al Chat ID del dipendente selezionato.

---

## 20. Gestione Dati (Import/Export)

### Accesso
**Dashboard** → **Gestione Dati** oppure URL: `/data-management/`

### Scarica Template Excel

Per ogni tipo di dato, puoi scaricare un file Excel pre-formattato con le colonne corrette:

| Template | Contenuto |
|----------|-----------|
| **Dipendenti** | Cognome, Nome, CF, Indirizzo, ecc. |
| **Clienti** | Ragione Sociale, P.IVA, Indirizzo, ecc. |
| **Mezzi** | Modello, Targa, Km, Scadenze, ecc. |
| **Qualifiche** | Nome, Descrizione |

### Importa Dati da Excel

1. Scarica il template appropriato
2. Compilalo con i dati
3. Nella pagina Gestione Dati, seleziona il **tipo di dato** e il **file**
4. Scegli la modalità:
   - **AGGIORNA**: Aggiorna record esistenti e crea nuovi
   - **SOVRASCRIVI**: Sostituisce tutti i dati
5. Clicca **"Importa"**

---

## 21. Backup e Ripristino

### Accesso
**Gestione Dati** → sezione **Backup e Ripristino**

> ⚠️ **Solo per Superuser** — Queste funzioni sono riservate agli utenti con permessi di superutente.

### Backup

Clicca **"Scarica Backup"** per scaricare un file JSON completo di tutti i dati del sistema. Il file viene nominato automaticamente con la data (es. `backup_kandor_20260303_2200.json`).

### Ripristino

1. Clicca **"Sfoglia"** e seleziona un file di backup JSON precedentemente scaricato
2. Clicca **"Ripristina"**
3. Il sistema caricherà tutti i dati dal backup

> ⚠️ **Attenzione**: Il ripristino sovrascrive i dati esistenti. Fai sempre un backup prima di ripristinare!

---

## 22. Widget Dashboard

La dashboard principale mostra dei widget informativi nella parte destra della pagina.

### 🚗 Scadenze Veicoli

Mostra i mezzi aziendali con scadenze (polizza o bollo) nei **prossimi 45 giorni** o già scadute.

| Indicatore | Significato |
|------------|-------------|
| 🔴 **Rosso** | Scadenza già passata |
| 🟠 **Arancione** | Scade entro 45 giorni (mostra i giorni rimanenti) |

### 🎂 Compleanni in Arrivo

Mostra i compleanni nei **prossimi 20 giorni** per:
- **Dipendenti** attivi (basato sulla data di nascita)
- **Referenti Clienti** (basato sulla data di nascita del referente)

### 📅 Pianificazione Settimanale

Mostra la vista settimanale dei turni con:
- Giorno della settimana e data
- Squadra assegnata e caposquadra
- Mezzo utilizzato
- Lista clienti con orari

Navigazione: usa le frecce **← Settimana precedente** / **Settimana successiva →**

Il giorno corrente è evidenziato.

### 📱 Feed Telegram

Mostra le ultime registrazioni ricevute via Telegram, divise in tre schede:

| Scheda | Contenuto |
|--------|-----------|
| **Ore Lavorate** | Ultime 10 registrazioni ore via Telegram |
| **Assenze** | Ultime 10 assenze segnalate via Telegram |
| **Segnalazioni** | Ultime 10 segnalazioni dai dipendenti |

Ogni voce mostra un'icona di stato (✅/⏳) che può essere cliccata per validare/processare.

---

## 23. FAQ e Risoluzione Problemi

### Il sito è lento al primo accesso

L'istanza gratuita di Render va in "standby" dopo 15 minuti di inattività. Il primo accesso dopo la pausa richiede ~50 secondi per il riavvio.

### Un dipendente non riceve i messaggi Telegram

1. Verifica che il **Telegram Chat ID** sia inserito correttamente nella sua scheda
2. Il dipendente deve aver avviato una conversazione con il bot almeno una volta
3. Il bot deve essere attivo e il webhook configurato

### Come ottenere il Chat ID di un dipendente

Il dipendente deve inviare un messaggio qualsiasi al bot. Se il suo Chat ID non è registrato, il bot risponderà con: `"Il tuo ID Telegram è: XXXXXXX"`. Copia quel numero e inseriscilo nella scheda del dipendente.

### Le coordinate GPS non vengono calcolate

- Assicurati che l'indirizzo sia completo (via, numero, città, provincia)
- Il servizio di geocodifica potrebbe essere temporaneamente non disponibile
- Riprova salvando nuovamente la scheda

### Gli errori di importazione Excel

- Scarica sempre il **template aggiornato** prima di importare
- Verifica che i dati rispettino i formati richiesti (date, numeri, ecc.)
- Il codice fiscale e la partita IVA devono essere univoci

### Come aggiungere un nuovo amministratore

Dall'admin panel, vai su **Utenti** → **Aggiungi Utente**. Imposta nome utente e password, poi nella scheda del nuovo utente attiva:
- ✅ Stato staff (per accedere al pannello)
- ✅ Stato superutente (per tutte le funzionalità)

---

> **Kandor** — Sistema ERP per la gestione operativa aziendale  
> Sviluppato per Studio Serra — © 2026
