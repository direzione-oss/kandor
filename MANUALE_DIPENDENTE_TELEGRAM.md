# 📱 Guida Rapida per il Dipendente — Bot Telegram Kandor

> **Versione**: 1.1 — Marzo 2026  
> Questa guida spiega come usare il bot Telegram aziendale per registrare ore, comunicare assenze e rispondere alle richieste di sostituzione.

---

## Come Iniziare

### 1. Installa Telegram
Scarica l'app **Telegram** dal Play Store (Android) o App Store (iPhone) se non ce l'hai già.

### 2. Avvia il Bot
Cerca su Telegram il bot **Kandor Assistente** (`@kandor_gestionale_bot`) oppure clicca il link diretto: [t.me/kandor_gestionale_bot](https://t.me/kandor_gestionale_bot).
Premi **"Avvia"** (o **"Start"**).

Puoi anche scansionare il QR Code qui sotto con la fotocamera del telefono:

![QR Code Bot Telegram Kandor](/static/core/img/qr_bot_telegram.png)

### 3. Registra il tuo ID
Quando invii il primo messaggio, il bot ti risponderà con: *"Non ti conosco! Il tuo ID Telegram è: XXXXXXX"*.  
**Comunica questo numero al tuo responsabile**, che lo inserirà nel sistema. Da quel momento sarai operativo!

---

## Il Menu Principale

Ogni volta che scrivi al bot, ricevi un **menu con bottoni**:

| Bottone | Cosa fa |
|---------|---------|
| **⏱ Registra Ore** | Inserisci le ore lavorative di oggi |
| **📋 Turni Non Compilati** | Vedi i turni degli ultimi 7 giorni senza ore inserite |
| **🤒 Malattia** | Comunica che sei in malattia oggi |
| **🏖️ Ferie** | Comunica che sei in ferie oggi |
| **📝 Permesso** | Comunica che hai un permesso oggi |
| **⚠️ Segnalazione** | Invia una segnalazione all'ufficio |
| **📖 Guida** | Apre questa guida nel browser |

---

## ⏱ Registrare le Ore Lavorate

### Passo dopo passo:

1. Premi **"⏱ Registra Ore"**
2. Il bot ti mostra **i turni di oggi** con il nome del cliente e l'orario previsto
3. **Tocca il turno** per il quale vuoi inserire le ore
4. **Scrivi il numero** di ore lavorate (es. `8` oppure `7.5`)
5. Il bot conferma: *"Salvate 8.0 ore per [Cliente]"*

### 📋 Turni Non Compilati

Se hai dimenticato di inserire le ore nei giorni passati:

1. Premi **"📋 Turni Non Compilati"**
2. Vedrai i turni degli **ultimi 7 giorni** senza ore inserite
3. Tocca quello da compilare e inserisci le ore

> ⚠️ **Importante**: Inserisci le ore **ogni giorno** dopo il turno di lavoro. Il responsabile le controlla e le valida per la busta paga.

---

## 🤒 Comunicare un'Assenza

Se non puoi lavorare oggi, premi il bottone corrispondente:

| Situazione | Bottone da premere | Cosa succede |
|------------|-------------------|--------------| 
| Sei malato | **🤒 Malattia** | Registrata assenza + verifica turni del giorno |
| Hai ferie | **🏖️ Ferie** | Registrate ferie + verifica turni del giorno |
| Hai un permesso | **📝 Permesso** | Registrato permesso + verifica turni del giorno |

Il sistema verifica automaticamente se hai turni oggi: se sì, avvia la procedura di sostituzione e notifica il Responsabile Area.

> 💡 **Consiglio**: Comunica l'assenza il prima possibile, idealmente al mattino presto così l'ufficio può organizzare un sostituto.

---

## ⚠️ Inviare una Segnalazione

Se devi segnalare un problema (es. attrezzatura rotta, situazione sul posto di lavoro):

1. Premi **"⚠️ Segnalazione"**
2. Il bot chiede: *"Scrivi il testo della segnalazione"*
3. Scrivi la segnalazione (es. *"Aspirapolvere rotto presso Hotel Roma"*)
4. Il bot conferma e la tua segnalazione arriva all'ufficio

### 📷 Puoi anche inviare una foto!

Se vuoi allegare una **foto** (es. del danno, del locale, della situazione), **inviala direttamente in chat** al bot — arriverà all'ufficio come messaggio con immagine e sarà visibile nel Centro Messaggi.

---

## 🔄 Richieste di Sostituzione

Se il tuo profilo è abilitato come **sostituto**, potresti ricevere richieste di copertura turni.

### Come funziona:

1. Ricevi un **messaggio con i dettagli** del turno da coprire:
   - 📍 **Cliente** e indirizzo
   - 📅 **Data** del turno
   - 🕐 **Orario** (inizio — fine)
   - 📏 **Distanza** da casa tua
   - 👥 **Compagni di squadra** con numero di telefono per contattarli

2. Hai **due bottoni**:
   - **✅ Accetto** → Confermi che andrai a coprire il turno
   - **❌ Rifiuto** → Non sei disponibile (la richiesta passa al prossimo)

3. Hai **1 ora** per rispondere. Se non rispondi, il sistema passa automaticamente al prossimo sostituto disponibile.

### Se accetti:

- Ricevi un messaggio di **conferma** con tutti i dettagli
- Presenta al turno nell'orario indicato
- **Contatta i compagni di squadra** se necessario (trovi i numeri nel messaggio)
- A fine turno, **registra le ore** come al solito

### Se rifiuti:

- Nessun problema! La richiesta passa al prossimo disponibile
- Non ci sono penalità per il rifiuto

---

## 💬 Risposte del Bot — Cosa Significano

| Messaggio del bot | Significato |
|-------------------|-------------|
| ✅ *"Salvate 8.0 ore per Hotel Roma"* | Ore registrate con successo |
| 🤒 *"Registrata MALATTIA per oggi"* | Assenza per malattia registrata |
| 🏖️ *"Ferie registrate per oggi"* | Ferie registrate |
| 📝 *"Ho preso nota della segnalazione"* | Segnalazione ricevuta dall'ufficio |
| ✅ *"Sostituzione CONFERMATA!"* | Hai accettato una sostituzione |
| 🚫 *"Non ti conosco!"* | Il tuo Chat ID non è registrato — contatta l'ufficio |
| ⚠️ *"Turno non trovato"* | Nessun turno disponibile per oggi |

---

## ❓ Domande Frequenti

### Non trovo i bottoni del menu
Scrivi qualsiasi messaggio al bot (anche solo "ciao") e il menu riapparirà.

### Ho inserito le ore sbagliate
Contatta l'ufficio, che potrà correggere le ore dal sistema.

### Non ho ricevuto la richiesta di sostituzione
Verifica di avere una connessione internet attiva e le notifiche Telegram abilitate.

### Come so se le mie ore sono state validate?
Le ore validate hanno un **✅** nel sistema. Se vedi **⏳** significa che sono in attesa di validazione da parte dell'ufficio.

### Devo comunicare l'assenza anche di persona?
Il bot registra l'assenza nel sistema, ma è buona norma **avvisare anche telefonicamente** il tuo responsabile, specialmente in caso di malattia improvvisa.

---

## 📞 Supporto

Per problemi con il bot o il sistema, contatta l'ufficio amministrativo.

---

> *Guida per i dipendenti — Sviluppato da Studio Serra — © 2026*
