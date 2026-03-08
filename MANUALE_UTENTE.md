# 📘 KANDOR — Manuale d'Uso Completo

> **Versione**: 2.0  
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
9b. [Titolari e Supervisione](#9b-titolari-e-supervisione)
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

## 9b. Titolari e Supervisione

### Accesso
**Dashboard** → **👁 Supervisione** oppure URL: `/titolari/`

I **Titolari** sono i proprietari/responsabili dell'azienda che vogliono avere una visione d'insieme senza entrare nel dettaglio operativo quotidiano.

### Cos'è un "Account di Accesso"?

Per creare un Titolare occorre prima creare un **account di accesso** al portale (username + password). Questo account è ciò che il titolare usa per fare login su `kandor.onrender.com`.

**Come crearlo:**
1. **Admin** → **Autenticazione e Autorizzazione** → **Utenti** → **Aggiungi Utente**
2. Scegli username e password
3. Salva e poi torna su **Core** → **Titolari** → **Aggiungi Titolare**
4. Collega l'utente appena creato e inserisci il **Telegram Chat ID** del titolare

### Campi del Titolare

| Campo | Descrizione |
|-------|-------------|
| **Utente Django** | Account di accesso al portale (username + password) |
| **Nome Completo** | Nome del titolare |
| **Telegram Chat ID** | ID Telegram per ricevere notifiche e riepilogo settimanale |
| **Notifiche Attive** | Abilita/disabilita i messaggi Telegram |

### Dashboard di Supervisione `/titolari/`

La dashboard mostra in tempo reale:

| Sezione | Contenuto |
|---------|-----------|
| **👥 Dipendenti** | Totale attivi, assenti oggi, sostituti abilitati |
| **📋 Turni di Oggi** | Pianificati, compilati, scoperti |
| **🔄 Sostituzioni** | Aperte in attesa RA, inviate, fallite oggi |
| **⚠️ Alert Economici** | Contratti sotto la soglia €/ora |
| **📆 Settimana** | Ore totali, turni, assenze, sostituzioni |

### Notifiche Telegram Automatiche

Il sistema invia notifiche ai titolari automaticamente:
- ✅ **Sostituzione confermata** — quando un sostituto accetta il turno
- 🚨 **Alert turno scoperto** — quando tutti i sostituti hanno rifiutato e il turno è rimasto scoperto

### Riepilogo Settimanale — Venerdì 18:00

Ogni venerdì alle 18:00 i titolari ricevono via Telegram un messaggio con:
- Dipendenti attivi, turni della settimana, ore registrate
- Assenze (malattia, ferie, permessi)
- Sostituzioni gestite
- Contratti sotto soglia

**Per inviarlo manualmente:**
1. **Admin** → **Titolari** → seleziona almeno un titolare
2. Azione → **"Invia riepilogo settimanale adesso"**

**Per il trigger automatico:** configurare [cron-job.org](https://cron-job.org) (gratuito) con:
- URL: `https://kandor.onrender.com/titolari/riepilogo/?token=TUA_CHIAVE`
- Giorno: ogni venerdì — Ora: 18:00
- Aggiungere `RIEPILOGO_TOKEN = "TUA_CHIAVE"` nelle variabili ambiente di Render


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

Questa pagina mostra un report dettagliato delle ore lavorate per ciascun dipendente e le assenze del mese.

### Come Usarlo

1. Seleziona **Mese** e **Anno** dai menu a tendina
2. Clicca **"Aggiorna"**

### Sezioni del Report

#### 1. Riepilogo per Cliente
Per ogni cliente con contratto attivo:
- **Ore Contratto** — ore mensili previste
- **Ore Lavorate** — ore registrate nel mese
- **Ore Validate** — solo le ore confermate (badge verde)
- **Differenza** — Lavorate − Contratto (verde = surplus, rosso = deficit)
- **€ Contratto / € Calcolato** — importi mensili

#### 2. Riepilogo per Squadra e Dipendente
Raggruppato per squadra, con le ore per ogni dipendente e il dettaglio dei clienti serviti. Cliccabile per espandere/chiudere.

#### 3. Riepilogo Assenze del Mese *(NUOVO)*
Tabella con tutte le assenze dei dipendenti nel mese selezionato:

| Colonna | Descrizione |
|---------|-------------|
| **Malattia** | Giorni di malattia |
| **Ferie** | Giorni di ferie |
| **Permesso** | Giorni di permesso |
| **L.104** | Giorni Legge 104 |
| **Altro** | Altre assenze |
| **Totale gg** | Somma giorni assenza |

Cliccando sul nome di un dipendente si espandono i dettagli delle singole assenze (date, tipo, note).

### Stampa PDF

Clicca **"🖨 Scarica PDF"** per generare il report completo in PDF:
- Tabella per cliente con ore e importi
- Tabella per squadra/dipendente
- Tabella assenze del mese (con dettaglio per dipendente)

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

### Registrazione via Telegram (assenza immediata)

I dipendenti comunicano l'assenza tramite i **bottoni inline** del bot (Malattia, Ferie, Permesso). Il sistema:
1. Registra l'assenza
2. **Verifica automaticamente** se il dipendente ha turni nella giornata
3. Per ogni turno scoperto: **avvia la procedura di sostituzione** (notifica al Responsabile Area)
4. Il dipendente riceve conferma con l'elenco dei turni interessati

### Ferie Programmate con Sostituzione Automatica *(NUOVO)*

Quando si crea un'assenza dall'Admin con date future (es. ferie 15→20 marzo), il sistema:
1. Al salvataggio, cerca tutti i turni del dipendente nel range di date
2. Per ogni turno trovato, crea automaticamente una **RichiestaSostituzione**
3. Il Responsabile Area riceve la notifica Telegram per approvare i sostituti
4. I sostituti vengono contattati in ordine di distanza e disponibilità

> 💡 **Anti-duplicati**: se esiste già una richiesta attiva per quel turno, non ne crea un'altra.

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
