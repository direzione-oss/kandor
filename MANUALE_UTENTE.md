# 📘 KANDOR — Manuale d'Uso Completo

> **Versione**: 2.1  
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
9. [Responsabili Area](#9-responsabili-area)
10. [Pianificazione Turni e Calendario](#10-pianificazione-turni-e-calendario)
11. [Programmazione Ricorrente](#11-programmazione-ricorrente)
12. [Richieste Straordinarie](#12-richieste-straordinarie)
13. [Gestione Sostituti](#13-gestione-sostituti)
14. [Registrazione Ore (Time Tracking)](#14-registrazione-ore-time-tracking)
15. [Verifica Ore Mensili](#15-verifica-ore-mensili)
16. [Gestione Assenze](#16-gestione-assenze)
17. [Segnalazioni](#17-segnalazioni)
18. [Riconciliazione Ore](#18-riconciliazione-ore)
19. [Analisi Economica Contratti](#19-analisi-economica-contratti)
20. [Integrazione Telegram](#20-integrazione-telegram)
21. [Messaggi Programmati](#21-messaggi-programmati)
22. [Centro Messaggi Telegram](#22-centro-messaggi-telegram)
23. [Gestione Dati (Import/Export)](#23-gestione-dati-importexport)
24. [Backup e Ripristino](#24-backup-e-ripristino)
25. [Widget Dashboard](#25-widget-dashboard)
26. [FAQ e Risoluzione Problemi](#26-faq-e-risoluzione-problemi)

---

## 1. Introduzione

**KANDOR** è un sistema ERP (Enterprise Resource Planning) progettato per la gestione operativa di imprese di servizi, in particolare aziende di pulizie e facility management. Il sistema permette di:

- **Gestire dipendenti** con dati anagrafici, qualifiche, stato e ruolo sostituto
- **Gestire clienti** con indirizzi, programmazione lavori e importi contrattuali
- **Pianificare turni** automaticamente con calendario settimanale interattivo
- **Tracciare le ore lavorate** in tempo reale, anche via Telegram
- **Gestire assenze** (malattia, ferie, permessi)
- **Gestire sostituti** con flusso di approvazione Responsabile Area e notifiche Telegram
- **Verificare ore mensili** con report dettagliati e PDF per l'amministrazione
- **Analizzare i contratti** per individuare quelli sotto soglia economica
- **Riconciliare le ore** previste vs lavorate per ogni cliente
- **Comunicare con i dipendenti** tramite Telegram (bottoni inline, assenze, ore)

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

### Barra Laterale — Operazioni Frequenti

| Link | Funzione |
|------|----------|
| **Trova Jolly** | Cerca sostituti disponibili |
| **Riconciliazione** | Confronta ore previste vs lavorate |
| **Analisi Contratti** | Analisi economica contratti sotto soglia |
| **Gestione Dati** | Import/Export dati Excel |
| **Guide** | Manuali (Admin + Dipendente) |
| **Centro Messaggi** | Chat diretta con i dipendenti via Telegram |
| **Genera Turni** | Genera turni automatici per 7 giorni |
| **Vedi Report** | Report verifica ore mensili con PDF |
| **Manuale** | Apri questo manuale |

### Sezione Risorse

Accesso a: Clienti, Dipendenti, Mezzi, Qualifiche, Squadre, Responsabili Area, Messaggi Programmati

### Sezione Operativa

Accesso a: Assegnazioni Turno, Assenze, Registrazioni Ore, Turni, Richieste Sostituzione

### Widget (Pannello Destro)

Vedi la sezione [Widget Dashboard](#25-widget-dashboard) per i dettagli.

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

#### Dati Contrattuali e Ruoli
| Campo | Descrizione |
|-------|-------------|
| **Categoria Protetta** | Checkbox, indica se è categoria protetta |
| **File Contratto** | Upload del file contratto (PDF, ecc.) |
| **Qualifiche Possedute** | Selezione multipla delle qualifiche |
| **Disponibile come Sostituto** | ✅ Se attivo, il dipendente può essere chiamato come sostituto |

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

- **Geocodifica automatica**: Quando inserisci l'indirizzo, il sistema calcola automaticamente le coordinate GPS. Queste vengono usate per il calcolo della distanza nella ricerca sostituti.
- **Data di nascita dal CF**: Se non inserisci la data di nascita, il sistema la estrarrà automaticamente dal codice fiscale.
- **Flag Sostituto**: I dipendenti con "Disponibile come Sostituto" attivo appariranno nella ricerca sostituti quando serve una copertura.

### Ricerca e Filtri

- **Barra di ricerca**: Cerca per cognome, nome, codice fiscale o Telegram Chat ID
- **Filtri laterali**: Filtra per stato, per flag sostituto (Sì/No) e per qualifiche

### Azione: Invia Messaggio Telegram

1. Seleziona uno o più dipendenti tramite le checkbox
2. Dal menu **"Azione"** in basso, scegli **"💬 Invia Messaggio Telegram"**
3. Clicca **"Esegui"**
4. Scrivi il messaggio nella pagina intermedia
5. Clicca **"Invia"**

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
| **Importo Mensile Contratto (€)** | Importo mensile concordato | ❌ |
| **Note Mansioni** | Descrizione delle mansioni richieste | ❌ |

### Sezioni Inline (nella scheda cliente)

#### Programmazione Ricorrente
Permette di definire gli appuntamenti fissi (settimanali, bisettimanali o mensili) per quel cliente.

#### Richieste Straordinarie
Permette di inserire lavori extra non ricorrenti.

### Azione: Duplica per Nuova Sede

Seleziona un cliente e usa l'azione **"📋 Duplica per nuova sede"** per creare una copia con tutti i dati, utile per clienti con più sedi.

---

## 6. Gestione Qualifiche

### Accesso
**Dashboard** → **Qualifiche**

Le qualifiche definiscono le competenze dei dipendenti (es. "Pulizie industriali", "Giardinaggio", "Sanificazione").

| Campo | Descrizione |
|-------|-------------|
| **Nome** | Nome della qualifica |
| **Descrizione** | Descrizione dettagliata (opzionale) |

Le qualifiche vengono usate nel sistema sostituti per filtrare candidati con competenze compatibili.

---

## 7. Gestione Mezzi Aziendali

### Accesso
**Dashboard** → **Mezzi Aziendali**

| Campo | Descrizione |
|-------|-------------|
| **Modello Mezzo** | Modello del veicolo (es. "Fiat Ducato") |
| **Targa** | Targa univoca del veicolo |
| **Stato Attuale** | Disponibile / In Manutenzione / In Riparazione |
| **Km Percorsi** | Chilometraggio attuale |
| **Scadenza Polizza** | Data scadenza assicurazione |
| **Scadenza Bollo** | Data scadenza bollo |

### Alert Scadenze

Il widget nella dashboard mostra i mezzi con scadenze nei prossimi 45 giorni o già scadute, ordinati per scadenza più vicina. Il widget si apre automaticamente se ci sono scadenze entro 7 giorni.

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

Nella lista squadre è visibile anche il **Responsabile Area** associato.

### Azione: Invia Messaggio alla Squadra

1. Seleziona una o più squadre
2. Scegli **"💬 Invia Messaggio alla Squadra"**
3. Scrivi il messaggio
4. Il messaggio verrà inviato a tutti i membri che hanno Telegram configurato

---

## 9. Responsabili Area

### Accesso
**Dashboard** → **Responsabili Area**

Il Responsabile Area è un ruolo **al di sopra delle squadre**. Supervisiona una o più squadre e approva le richieste di sostituzione.

| Campo | Descrizione |
|-------|-------------|
| **Dipendente** | Il dipendente che ricopre il ruolo di RA |
| **Nome Area** | Nome dell'area gestita (es. "Area Nord", "Area Centro") |
| **Squadre Supervisionate** | Selezione multipla delle squadre sotto la sua responsabilità |

### Ruolo nel Sistema Sostituti

Quando viene creata una richiesta di sostituzione per una squadra, il sistema:
1. Cerca il Responsabile Area associato a quella squadra
2. Gli invia una notifica Telegram con i dettagli
3. Il RA approva o rifiuta la sostituzione
4. Solo dopo l'approvazione il sostituto viene contattato

---

## 10. Pianificazione Turni e Calendario

### Accesso
**Dashboard** → **Turni** oppure usa il **Calendario Settimanale** nella dashboard

### Calendario Interattivo

La dashboard mostra un **calendario settimanale** con vista oraria:

- **Navigazione**: Frecce ← / → per cambiare settimana, filtri per squadra
- **Visualizzazione**: Ogni evento mostra il cliente, la squadra e un badge colorato per le ore
- **Interazione**: Clicca su un evento per vedere i dettagli

### Dettaglio Turno (click su un evento)

Si apre un modal con:
- **Cliente** (link alla scheda)
- **Squadra** (link alla scheda)
- **Orario** previsto
- **Note**
- **Ore dichiarate** con stato (verde=validato, giallo=da validare, rosso=mancanti)
- **Inserimento ore** diretto per l'admin
- **Bottoni**: Valida Ore, 🔄 Trova Sostituto, Elimina, Salva Modifiche

### Aggiungere un Nuovo Turno

Clicca il **"+"** sulla cella del calendario → compila: Tipo (Ricorrente/Straordinario), Squadra, Cliente, Orari, Note → Salva.

### Generazione Automatica Turni

Dalla sidebar, clicca **"Genera Turni"** per creare le assegnazioni per i prossimi 7 giorni basandosi sulle programmazioni ricorrenti.

### Badge Ore nel Calendario

| Colore | Significato |
|--------|-------------|
| 🟢 **Verde** | Ore validate dall'admin |
| 🟡 **Giallo** | Ore dichiarate, in attesa di validazione |
| 🔴 **Rosso** | Ore non ancora dichiarate |
| ⚪ **Nessuno** | Turno futuro |

---

## 11. Programmazione Ricorrente

Accessibile dalla **scheda del Cliente** (sezione inline).

| Campo | Descrizione |
|-------|-------------|
| **Tipo Ripetizione** | Settimanale / Bisettimanale / Mensile |
| **Giorno della Settimana** | Per ripetizione settimanale (Lunedì-Domenica) |
| **Giorno del Mese** | Per ripetizione mensile (1-31) |
| **Ora Inizio** | Orario di inizio (formato HH:MM) |
| **Durata** | Durata in ore (es. 2.5 = 2 ore e 30 minuti) |
| **Ora Fine** | ⚡ Calcolata automaticamente |
| **Orario Flessibile** | Se attivo, gli orari sono indicativi |
| **Mansione/Qualifica** | Qualifica richiesta per questo lavoro |
| **Squadra Abituale** | La squadra che normalmente svolge il lavoro |
| **Mezzo Abituale** | Il veicolo normalmente utilizzato |
| **Data Inizio Contratto** | Data dalla quale iniziano i turni |
| **Data Fine Contratto** | Data fine (vuoto = a tempo indeterminato) |

### Validazioni Automatiche

- Verifica che non ci siano **sovrapposizioni orarie** per la stessa squadra o mezzo
- Per ripetizione **Bisettimanale**, è obbligatoria la Data Inizio Contratto

---

## 12. Richieste Straordinarie

Accessibili dalla **scheda del Cliente** (sezione inline).

| Campo | Descrizione |
|-------|-------------|
| **Data Inizio** | Data del lavoro straordinario |
| **Data Fine** | Data di fine (se più giorni) |
| **Ora Inizio/Fine** | Orari del lavoro |
| **Descrizione Attività** | Cosa bisogna fare |
| **Completata** | Checkbox per segnare come completata |

---

## 13. Gestione Sostituti

### Panoramica

Il sistema sostituti permette di gestire la copertura di dipendenti assenti con un flusso strutturato:

1. **Admin** identifica un turno scoperto nel calendario
2. Clicca **"🔄 Trova Sostituto"** nel dettaglio turno
3. Il sistema mostra la lista dei sostituti disponibili ordinata per distanza
4. L'admin seleziona il dipendente assente e il motivo, poi invia la richiesta
5. Il **Responsabile Area** riceve una notifica Telegram e approva/rifiuta
6. Il **sostituto** riceve il dettaglio completo: cliente, indirizzo, orari, compagni di squadra con contatti
7. Il sostituto ha **1 ora** per accettare. Se non risponde, il sistema passa al successivo

### Come Usare il Bottone "Trova Sostituto"

1. Nel **calendario settimanale**, clicca su un turno
2. Nel modal, clicca **"🔄 Trova Sostituto"**
3. Appare un pannello con la **tabella dei sostituti** (Nome, Distanza, Qualifiche, Telefono)
4. Seleziona il **motivo assenza** e il **dipendente assente**
5. Clicca **"📩 Invia Richiesta al Responsabile Area"**

### Criteri di Ricerca Sostituti

Il sistema filtra automaticamente i candidati che:
- ✅ Sono in stato **ATTIVO** e hanno il flag **"Disponibile come Sostituto"**
- ✅ **NON** sono in ferie/malattia/permesso in quella data
- ✅ **NON** sono già impegnati in un turno sovrapposto
- ✅ Possiedono la **qualifica** compatibile (se richiesta)

I risultati sono ordinati per **distanza** (indirizzo del dipendente → indirizzo del cliente).

### Messaggio al Sostituto via Telegram

Il sostituto riceve un messaggio con:
- 📍 Cliente e indirizzo
- 📅 Data e 🕐 orario
- 📏 Distanza da casa
- 👥 Compagni di squadra con numeri di telefono
- Bottoni **"✅ Accetto"** / **"❌ Rifiuto"**

### Pannello Admin — Richieste Sostituzione

**Dashboard** → **Richieste Sostituzione**

| Colonna | Descrizione |
|---------|-------------|
| **Data creazione** | Quando è stata creata la richiesta |
| **Data turno** | Data del turno da coprire |
| **Cliente** | Il cliente interessato |
| **Dipendente assente** | Chi è assente |
| **Motivo** | Malattia, Ferie, Permesso, ecc. |
| **Sostituto** | Chi è stato assegnato |
| **Stato** | Aperta / Approvata RA / Inviata / Accettata / Completata / Annullata |
| **Distanza km** | Distanza casa-cliente del sostituto |

Azione rapida: **"✅ Approva e invia ai sostituti"** per approvare in blocco.

---

## 14. Registrazione Ore (Time Tracking)

### Accesso
**Dashboard** → **Time Tracking** oppure via **Telegram**

| Campo | Descrizione |
|-------|-------------|
| **Dipendente** | Chi ha lavorato |
| **Assegnazione** | L'assegnazione turno collegata |
| **Ore Dichiarate** | Numero di ore lavorate |
| **Origine** | Manuale, Telegram o WhatsApp |
| **Validato** | Checkbox per conferma amministrativa |

### Validazione Ore dal Calendario

Nel calendario, le ore non validate mostrano un badge **giallo**. Clicca sull'evento → bottone **"✅ Valida Ore"** per confermarle (diventano verdi). Per rimuovere la validazione: **"❌ Rimuovi Validazione"**.

### Inserimento Ore dall'Admin

Nell'evento del calendario: campo "Inserisci ore lavorate" con checkbox "Valida subito" → **"💾 Salva Ore"**.

---

## 15. Verifica Ore Mensili

### Accesso
**Dashboard** → **Vedi Report** (nelle Operazioni Frequenti) oppure URL: `/verifica-ore/`

Questa pagina mostra un report dettagliato delle ore lavorate per ciascun dipendente in un dato mese.

### Come Usarlo

1. Seleziona **Mese** e **Anno** dai menu a tendina
2. Clicca **"Aggiorna"**

### Informazioni Mostrate

Per ogni dipendente:
- **Ore Contrattuali** (somma delle ore previste dai turni del mese)
- **Ore Lavorate** (solo ore **validate** — badge verde)
- **Differenza** (Lavorate − Contrattuali, positiva o negativa)

### Struttura del Report

Il report mensile è suddiviso in **tre tabelle**:

1. **Riepilogo per Cliente** — ore contratto, ore lavorate, ore validate, differenza, importo
2. **Riepilogo per Squadra e Dipendente** — ore totali per squadra con dettaglio per dipendente
3. **Riepilogo Assenze del Mese** — tabella con i giorni di assenza per ogni dipendente suddivisi per tipo

### Tabella Assenze nel Report

| Colonna | Descrizione |
|---------|-------------|
| **Dipendente** | Nome e cognome |
| **Malattia** | Giorni di malattia nel mese |
| **Ferie** | Giorni di ferie nel mese |
| **Permesso** | Giorni di permesso |
| **L.104** | Giorni Legge 104 |
| **Altro** | Altre tipologie |
| **Totale gg** | Totale giorni assenza |

> 💡 Clicca sul nome di un dipendente nella tabella assenze per espandere il **dettaglio** di ogni singola assenza (date, tipo, note).

### Stampa PDF

Clicca **"📄 Scarica PDF"** — il PDF contiene tutte e tre le tabelle, incluse le assenze del mese.

> ⚠️ **Importante**: Nel report vengono contabilizzate **solo le ore validate** (badge verde nel calendario).

---

## 16. Gestione Assenze

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

### 🚨 Alert Automatico Assenza → Sostituzione

Quando un dipendente comunica **Malattia, Ferie o Permesso** tramite Telegram, il sistema:

1. Registra l'assenza
2. **Verifica automaticamente** se il dipendente ha turni nella giornata corrente
3. Se trova turni scoperti, **avvia la procedura di sostituzione** per ciascuno
4. Notifica il **Responsabile Area** via Telegram
5. Il dipendente riceve una conferma con il numero di turni scoperti

Esempio di risposta al dipendente:
```
Registrata MALATTIA per oggi (08/03). Riposati!

⚠️ ATTENZIONE: Hai 2 turno/i oggi!
  • Hotel Roma (06:00-14:00)
  • Centro Pulizie (14:30-18:00)

🔄 Procedura sostituzione avviata per 2 turno/i.
Il Responsabile Area è stato notificato.
```

### 📅 Ferie Programmate (date future)

Quando si crea un'assenza dall'admin per **date future** (anche su più giorni), il sistema:

1. Cerca tutti i turni del dipendente nel range di date dell'assenza
2. Per ogni turno trovato, crea automaticamente una `RichiestaSostituzione`
3. Notifica il **Responsabile Area** per ciascun turno
4. L'admin riceve un riepilogo completo via Telegram (se `TELEGRAM_ADMIN_CHAT_ID` è configurato)

> 💡 **Anti-duplicati**: se per quel turno esiste già una richiesta di sostituzione attiva, non viene creata una nuova.

### Registrazione via Telegram

I dipendenti possono comunicare assenze tramite i **bottoni inline** del bot Telegram: Malattia, Ferie, Permesso. Il sistema attiverà automaticamente l'alert sostituzione se ci sono turni.

---

## 17. Segnalazioni

Le segnalazioni vengono inviate dai dipendenti tramite Telegram.

| Campo | Descrizione |
|-------|-------------|
| **Dipendente** | Chi ha fatto la segnalazione |
| **Testo** | Contenuto della segnalazione |
| **Data Inserimento** | Quando è stata inserita |
| **Risolto** | Checkbox per chiudere la segnalazione |
| **Note Amministrazione** | Risposta dell'amministratore |

---

## 18. Riconciliazione Ore

### Accesso
**Dashboard** → **Riconciliazione** oppure URL: `/reconciliation/`

Confronta le **ore contrattuali** con le **ore lavorate** per ogni cliente in un mese.

| Colore | Significato |
|--------|-------------|
| 🟢 **Verde (OK)** | Differenza entro ±5 ore |
| 🟠 **Arancione (WARNING)** | Più di +5 ore |
| 🔴 **Rosso (ALARM)** | Meno di −5 ore |

---

## 19. Analisi Economica Contratti

### Accesso
**Dashboard** → **Analisi Contratti** oppure URL: `/analisi-contratti/`

Analizza i contratti sotto soglia economica, mostrando:

- Importo mensile e orario per ogni cliente
- Ore previste vs ore effettive
- Contratti sotto la soglia minima
- Report PDF scaricabile

---

## 20. Integrazione Telegram

### Configurazione Iniziale

Il bot Telegram aziendale si chiama **Kandor Assistente** (`@kandor_gestionale_bot`).  
Link diretto: [t.me/kandor_gestionale_bot](https://t.me/kandor_gestionale_bot)

1. Ogni dipendente deve cercare **Kandor Assistente** su Telegram o cliccare il link sopra
2. Il bot comunicherà il proprio **Chat ID**
3. L'amministratore inserisce il Chat ID nella scheda del dipendente

### Menu Bot (Bottoni Inline)

All'invio di qualsiasi messaggio, il bot risponde con un **menu a bottoni**:

| Bottone | Azione |
|---------|--------|
| **📊 Registra Ore** | Mostra i turni di oggi, seleziona e inserisci ore |
| **📋 Turni Mancanti** | Mostra turni senza ore degli ultimi 7 giorni |
| **🤒 Malattia** | Registra assenza malattia per oggi |
| **🏖️ Ferie** | Registra ferie per oggi |
| **📝 Permesso** | Registra permesso per oggi |
| **⚠️ Segnalazione** | Avvia segnalazione testuale |

### Flusso Registrazione Ore

1. Il dipendente preme **"📊 Registra Ore"**
2. Il bot mostra i turni di oggi con cliente e orari
3. Il dipendente seleziona il turno
4. Scrive il numero di ore (es. "8" o "7.5")
5. Le ore vengono salvate nel sistema

### Notifiche Sostituzione

I **Responsabili Area** ricevono richieste di approvazione con bottoni **"✅ Approva"** / **"❌ Rifiuta"**.

I **Sostituti** ricevono proposte dettagliate con bottoni **"✅ Accetto"** / **"❌ Rifiuto"** e hanno 1 ora per rispondere.

---

## 21. Messaggi Programmati

### Accesso
**Dashboard** → **Messaggi Programmabili**

| Campo | Descrizione |
|-------|-------------|
| **Titolo** | Titolo/descrizione del messaggio |
| **Testo** | Contenuto del messaggio |
| **Data e Ora di Invio** | Quando inviare |
| **Destinatari Specifici** | Selezione multipla dei dipendenti |
| **Invia a TUTTI** | Se attivo, invia a tutti i dipendenti attivi |
| **Inviato** | Stato dell'invio (automatico) |

---

## 22. Centro Messaggi Telegram

### Accesso
**Dashboard** → **Centro Messaggi** oppure URL: `/chat-simulator/`

Il Centro Messaggi è una vera **chat bidirezionale** che permette di comunicare con i dipendenti via Telegram direttamente dalla piattaforma web.

### Funzionalità

| Funzione | Descrizione |
|----------|-------------|
| **Chat individuale** | Seleziona un dipendente dal pannello sinistro per vedere la cronologia dei messaggi e inviarne di nuovi |
| **Messaggi non letti** | Badge rosso sul nome di chi ha messaggi non letti |
| **Broadcast a tutti** | Invia un messaggio a tutti i dipendenti attivi con Telegram configurato |
| **Invio per squadra** | Seleziona una squadra e invia il messaggio a tutti i componenti |
| **Foto** | Supporto alla visualizzazione di foto inviate dai dipendenti |
| **Cronologia** | Ultimi 50 messaggi per ogni conversazione (IN e OUT) |

---

## 23. Gestione Dati (Import/Export)

### Accesso
**Dashboard** → **Gestione Dati** oppure URL: `/data-management/`

### Scarica Template Excel

| Template | Contenuto |
|----------|-----------|
| **Dipendenti** | Cognome, Nome, CF, Indirizzo, ecc. |
| **Clienti** | Ragione Sociale, P.IVA, Indirizzo, ecc. |
| **Mezzi** | Modello, Targa, Km, Scadenze, ecc. |
| **Qualifiche** | Nome, Descrizione |

### Importa Dati

1. Scarica il template, compilalo
2. Seleziona tipo di dato e file
3. Scegli modalità: **AGGIORNA** (update + crea) o **SOVRASCRIVI** (sostituisci)
4. Clicca **"Importa"**

---

## 24. Backup e Ripristino

### Accesso
**Gestione Dati** → sezione **Backup e Ripristino**

> ⚠️ **Solo per Superuser**

- **Backup**: Scarica un JSON completo del database
- **Ripristino**: Carica un backup precedente (sovrascrive i dati!)

---

## 25. Widget Dashboard

La dashboard mostra widget informativi collassabili nella parte destra.

### 🚗 Scadenze Veicoli (Collassabile)

- **Chiuso di default**, si apre automaticamente se ci sono scadenze entro 7 giorni
- Mostra mezzi con scadenze polizza/bollo nei prossimi 45 giorni
- Ordinati dal più urgente al meno urgente
- 🔴 Rosso = scaduto | 🟠 Arancione = scade entro 45 giorni
- Cliccando l'intestazione ▶/▼ si apre/chiude

### 🎂 Compleanni in Arrivo (Collassabile)

- **Chiuso di default**, si apre automaticamente se ci sono compleanni entro 7 giorni
- Mostra i compleanni nei prossimi 20 giorni
- Include dipendenti attivi e referenti clienti

### 📅 Pianificazione Settimanale

- Vista settimanale dei turni con calendario interattivo
- Badge colorati per ore (verde/giallo/rosso)
- Click per dettaglio, modifica, inserimento ore e ricerca sostituti

### 📱 Feed Telegram

Mostra le ultime registrazioni via Telegram:

| Scheda | Contenuto |
|--------|-----------|
| **Ore Lavorate** | Ultime 10 registrazioni ore |
| **Assenze** | Ultime 10 assenze segnalate |
| **Segnalazioni** | Ultime 10 segnalazioni |

### 📋 Scadenze Contratti

Mostra i contratti con programmazione ricorrente in scadenza prossima, con possibilità di proroga rapida.

---

## 26. FAQ e Risoluzione Problemi

### Il sito è lento al primo accesso

L'istanza Render va in standby dopo 15 minuti di inattività. Il riavvio richiede ~50 secondi.

### Un dipendente non riceve i messaggi Telegram

1. Verifica il **Telegram Chat ID** nella scheda dipendente
2. Il dipendente deve aver avviato una conversazione con il bot
3. Il bot deve essere attivo con webhook configurato

### Come ottenere il Chat ID

Il dipendente invia un messaggio al bot. Se non registrato, il bot risponde: *"Non ti conosco! Il tuo ID Telegram è: XXXXXXX"*. Inserire quel numero nella scheda dipendente.

### Le coordinate GPS non funzionano

- Inserire indirizzo completo (via, numero, città, provincia)
- Riprovare salvando nuovamente la scheda

### Non trovo sostituti disponibili

- Verificare che esistano dipendenti con **"Disponibile come Sostituto"** attivo
- Verificare che abbiano **qualifiche compatibili**
- Verificare che non siano **assenti o già impegnati** in quel giorno

### Come configurare il Responsabile Area

1. Vai in **Admin → Responsabili Area → Aggiungi**
2. Seleziona il dipendente
3. Dai un nome all'area
4. Assegna le squadre supervisionate

---

> **Kandor** — Sistema ERP per la gestione operativa aziendale  
> Sviluppato da Studio Serra — © 2026
