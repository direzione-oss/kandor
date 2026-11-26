"""
Dati e testo del Podcast Kandor ERP per Responsabili e Coordinatori.
"""

CAPITOLI_PODCAST = [
    {
        "id": 1,
        "titolo": "Introduzione e Visione Aziendale",
        "durata_stimata": "00:00",
        "descrizione": "Il ruolo chiave del Responsabile di Area, stop ai fogli volanti e gestione in tempo reale."
    },
    {
        "id": 2,
        "titolo": "Anagrafiche, Squadre, Sostituti e Jolly",
        "durata_stimata": "00:52",
        "descrizione": "Come funzionano le squadre, la differenza tra il ruolo di Sostituto e la figura del Jolly."
    },
    {
        "id": 3,
        "titolo": "Pianificazione Turni e Calendario",
        "durata_stimata": "01:50",
        "descrizione": "La programmazione ricorrente automatica, visualizzazione a colori e cambio turni."
    },
    {
        "id": 4,
        "titolo": "Rilevazione Ore, Telegram e Web App",
        "durata_stimata": "02:40",
        "descrizione": "Come gli operatori e i capisquadra inviano le ore e il Revisore Ore 1-Click."
    },
    {
        "id": 5,
        "titolo": "Assenze, Malattie e Smart Sostituzioni IA",
        "durata_stimata": "03:45",
        "descrizione": "Copertura automatica delle assenze: calcolo distanze chilometriche, qualifiche e notifiche a catena."
    },
    {
        "id": 6,
        "titolo": "Cantieri, SLA, Dotazioni Personali e Registro DPI",
        "durata_stimata": "04:55",
        "descrizione": "Note cliente, richieste materiali magazzino, vestiario, registro DPI con timbro/firma Kandor e restituzioni."
    },
    {
        "id": 7,
        "titolo": "Procedure, Cronologia UNDO, Buste Paga e Crediti IA",
        "durata_stimata": "05:48",
        "descrizione": "Rollback lavorazioni, invio cedolini crittografati su Telegram/WhatsApp, monitoraggio crediti IA Gemini 2.5."
    },
    {
        "id": 8,
        "titolo": "Invio Calendario Presenze Telegram e le 3 Regole d'oro",
        "durata_stimata": "06:40",
        "descrizione": "Invio PDF presenze ai lavoratori con blocco ore non validate e la routine quotidiana del Responsabile."
    }
]

TEXT_PODCAST = """
Benvenuti a questa guida audio ufficiale di Kandor ERP, il gestionale operativo di Studio Serra e delle nostre aziende partner. 
Questo podcast è stato preparato appositamente per voi: responsabili di area, capisquadra, coordinatori operativi e figure amministrative. 

Il nostro obiettivo è semplice: aiutarvi a comprendere la logica di Kandor in pochi minuti, per rendere il vostro lavoro quotidiano più veloce, ordinato e privo di stress. 
Dimenticate i vecchi fogli volanti, i messaggi sparsi su chat private e le ore perse a fine mese per far quadrare i conti. Con Kandor tutto è collegato in tempo reale.

Mettetevi comodi: nei prossimi minuti esploreremo insieme l'intero sistema, capitolo per capitolo.

Capitolo uno: La visione aziendale e il ruolo del Responsabile di Area.
Kandor nasce attorno a tre pilastri fondamentali: tracciabilità totale, comunicazione immediata con gli operatori e automazione intelligente. 
In quanto responsabili, voi siete il ponte fondamentale tra la direzione, i clienti e le squadre che operano ogni giorno sul campo. 
Kandor non è uno strumento di controllo rigido, ma un vero e proprio assistente digitale che vi toglie il carico mentale delle emergenze, segnalandovi solo ciò che richiede davvero la vostra attenzione.

Capitolo due: Anagrafiche, Squadre e Ruoli Speciali.
Al centro di Kandor ci sono le persone. Nella sezione Dipendenti ogni collaboratore ha una scheda completa con recapiti, visite mediche, corsi di sicurezza, coordinate GPS e il collegamento all'account Telegram. 
Qui troviamo due ruoli strategici che dovete conoscere benissimo: il ruolo di Sostituto e il ruolo di Jolly.
Il Sostituto è un operatore disponibile a intervenire quando un collega si assenta per malattia, infortunio o permesso. Solo chi ha questo flag attivo riceverà le richieste automatiche di copertura. 
Il Jolly, invece, è la figura flessibile dedicata a turni straordinari, cantieri speciali o picchi di lavoro imprevisti. 
Le squadre possono essere composte da uno o più operatori con un caposquadra designato. Ricordate sempre: ogni turno deve avere una squadra collegata, anche se formata da un singolo operatore. In questo modo il sistema sa sempre esattamente chi è responsabile del cantiere.

Capitolo tre: Pianificazione dei Turni e Calendario Operativo.
La forza di Kandor risiede nella Programmazione Ricorrente. 
I servizi regolari settimanali o mensili sono configurati come programmazioni automatiche. Ogni settimana il calendario genera in automatico tutti i turni con orari di inizio, fine, cantiere assegnato e l'eventuale furgone aziendale abbinato. 
Dalla schermata iniziale del Calendario avete una visione d'insieme chiara e colorata: vedete i cantieri coperti, le fasce orarie e potete spostare o modificare un turno con un semplice clic in caso di variazioni concordate con il cliente.

Capitolo quattro: Rilevazione Ore, il Bot Telegram e la Web App.
Come registrano le ore i lavoratori? In modo semplicissimo, senza dover installare applicazioni complesse.
Tutto avviene tramite il Bot Telegram ufficiale di Kandor oppure tramite la Web App per smartphone.
Al termine del servizio, il lavoratore apre il bot Telegram. Trova comodi pulsanti veloci: basta toccare Registra Ore e confermare l'orario, oppure scrivere un semplice messaggio, ad esempio "oggi 4 ore". L'intelligenza artificiale di Kandor riconosce il cantiere e registra le presenze.
Se una squadra lavora insieme, il caposquadra può registrare le ore per tutti i colleghi contemporaneamente, notificando ciascuno di loro in tempo reale.
E per voi responsabili? Avete a disposizione lo strumento "Revisore Ore 1-Click": a colpo d'occhio vedete le ore pianificate a contratto rispetto a quelle dichiarate dagli operatori. Se tutto corrisponde, basta un clic per validare la giornata e trasferire il dato alle paghe.

Capitolo cinque: Gestione Assenze, Malattie e Smart Sostituzioni con Intelligenza Artificiale.
Cosa succede quando un dipendente si ammala o richiede un permesso urgente?
Il dipendente può comunicare l'assenza direttamente dal bot Telegram, allegando la data o la foto del certificato medico.
Non appena l'assenza viene convalidata, entra in azione il motore di Smart Sostituzione IA di Kandor:
Invece di farvi fare decine di telefonate a vuoto, l'algoritmo analizza all'istante tutti i dipendenti sostituti disponibili, calcola la vicinanza chilometrica rispetto al cantiere, verifica le qualifiche necessarie e crea una graduatoria automatica.
Il sistema invia una notifica discreta al primo candidato disponibile. Se accetta, il turno viene aggiornato immediatamente sul calendario. Se rifiuta o non risponde entro un tempo prestabilito, il sistema passa automaticamente al candidato successivo. In ogni momento il Responsabile di Area riceve un riepilogo trasparente ed è libero di intervenire o confermare manualmente.

Capitolo sei: Cantieri, Clienti, SLA, Dotazioni Personali e Registro DPI.
Nella scheda di ciascun Cliente trovate l'indirizzo esatto geolocalizzato, le note operative speciali, le specifiche sui materiali e le ore mensili previste da contratto, con gestione automatica delle festività nazionali, del patrono di Brembate di Sopra e delle sospensioni per ferie cliente.
Dal campo, i lavoratori possono inviare segnalazioni urgenti e richiedere materiali, ma non solo: con il nuovo modulo Dotazioni Personali e Registro DPI, l'ufficio gestisce in modo impeccabile la consegna di divise, vestiario da lavoro e dispositivi di protezione individuale previsti dal Testo Unico sulla Sicurezza.
È possibile modificare la data di consegna reale, registrare la restituzione degli indumenti a fine rapporto e stampare il verbale ufficiale di consegna DPI con timbro e firma aziendale Kandor, pronto per la firma del dipendente.
Inoltre, attraverso il modulo Ispezioni Qualità, potete compilare direttamente da smartphone la scheda di audit periodica sul cantiere, con punteggio SLA e firma digitale.

Capitolo sette: Procedure Operative, Cronologia Rollback UNDO, Buste Paga e Credito IA.
Kandor integra anche un potente modulo Procedure: per qualsiasi attività aziendale importante potete avviare una checklist guidata con avvalli bloccanti tra colleghi. 
E se si commette un errore operativo? Niente panico: con il nuovo modulo Cronologia Lavorazioni e Rollback UNDO, potete visualizzare lo storico delle azioni e annullare con un clic modifiche indesiderate, con permessi profilati per ciascun responsabile.
Per la parte economica, il sistema include la Pre-Fatturazione con alert per i dati fiscali mancanti dei clienti e il monitoraggio trasparente del Credito IA basato sul potente motore Gemini 2.5 Flash.
Infine, con un clic, l'amministrazione può dividere i file PDF cumulativi delle buste paga e inviare a ciascun dipendente il proprio cedolino personale direttamente su Telegram o WhatsApp, protetto e crittografato.

Capitolo otto: Invio Calendario Presenze via Telegram e le 3 Regole d'oro del Responsabile.
Novità fondamentale per la trasparenza con i lavoratori: dalla sezione Cedolini Paghe potete inviare con un solo tocco il PDF del Calendario Presenze mensile direttamente sulla chat Telegram del singolo dipendente o di tutti i collaboratori in blocco. 
E per garantire la massima correttezza retributiva, il sistema include un blocco di sicurezza automatico: se nella mensilità sono presenti turni con ore non ancora validate, l'invio del calendario viene bloccato finché il responsabile non effettua la validazione!
Per ottenere il massimo da Kandor senza alcuno sforzo, vi ricordiamo la semplice routine giornaliera in tre passi:
Regola numero uno: Al mattino, date uno sguardo veloce al cruscotto iniziale per verificare che tutti i turni della giornata abbiano una squadra assegnata e che non ci siano segnalazioni o assenze impreviste.
Regola numero due: Durante il giorno, se ricevete una notifica dal Bot Telegram per una sostituzione o un materiale mancante, prendete in carico la richiesta con i tasti rapidi: ci vogliono meno di dieci secondi.
Regola numero tre: A fine giornata o al mattino successivo, aprite il Revisore Ore: controllate le presenze caricate dai capisquadra e cliccate su Valida. Questo garantirà una rendicontazione impeccabile e paghe puntuali e corrette per tutti.

In conclusione: Kandor è stato costruito per rendere il vostro lavoro più sereno, valorizzare la vostra professionalità sul territorio e garantire ai nostri clienti un servizio impeccabile.
Questo podcast e tutti i manuali operativi in PDF e interattivi restano sempre a vostra disposizione nella sezione Manuali del portale. 

Grazie per la vostra attenzione, per il vostro impegno quotidiano e buon lavoro con Kandor ERP!
""".strip()
