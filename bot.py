# [Aggiungi questi import all'inizio del file]
from datetime import datetime, time, timedelta
import asyncio
import logging

# Configura il logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def genera_e_invia_pdf_giornaliero(application):
    try:
        # Genera il PDF
        file_pdf = genera_pdf()
        logger.info("PDF giornaliero generato con successo")

        # Ottieni gli utenti dal database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT chat_id FROM utenti")
        utenti = c.fetchall()
        conn.close()
        
        # Conta gli invii riusciti
        invii_riusciti = 0
        
        # Invia a ogni utente
        for utente in utenti:
            try:
                await application.bot.send_document(
                    chat_id=utente['chat_id'],
                    document=open(file_pdf, 'rb'),
                    filename=f"segnalazioni_{datetime.now().strftime('%Y%m%d')}.pdf",
                    caption="📊 Report giornaliero delle segnalazioni\n"
                           f"Data: {datetime.now().strftime('%d/%m/%Y')}"
                )
                invii_riusciti += 1
                logger.info(f"PDF inviato con successo all'utente {utente['chat_id']}")
                await asyncio.sleep(1)  # Pausa tra gli invii
                
            except Exception as e:
                logger.error(f"Errore nell'invio del PDF all'utente {utente['chat_id']}: {str(e)}")
        
        # Pulisci il file PDF
        os.remove(file_pdf)
        logger.info(f"PDF inviato a {invii_riusciti} utenti su {len(utenti)}")
        
    except Exception as e:
        logger.error(f"Errore nella generazione/invio del PDF giornaliero: {str(e)}")

async def scheduler_pdf_giornaliero(application):
    while True:
        try:
            now = datetime.now()
            # Imposta gli orari di invio (20:00 e 08:00)
            orari_invio = [
                time(hour=20, minute=0),
                time(hour=8, minute=0)
            ]
            
            # Trova il prossimo orario di invio
            prossimo_invio = None
            for orario in orari_invio:
                target = now.replace(hour=orario.hour, minute=orario.minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                if prossimo_invio is None or target < prossimo_invio:
                    prossimo_invio = target

            # Calcola il tempo di attesa
            wait_seconds = (prossimo_invio - now).total_seconds()
            logger.info(f"Prossimo invio PDF programmato per: {prossimo_invio}")
            
            await asyncio.sleep(wait_seconds)
            await genera_e_invia_pdf_giornaliero(application)
            
        except Exception as e:
            logger.error(f"Errore nello scheduler: {str(e)}")
            await asyncio.sleep(300)  # Attendi 5 minuti in caso di errore

# Modifica la funzione init_db per includere la tabella utenti
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Tabella segnalazioni
        c.execute('''CREATE TABLE IF NOT EXISTS segnalazioni
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     turno TEXT, 
                     segnalazione TEXT,
                     data TEXT)''')
        
        # Tabella utenti
        c.execute('''CREATE TABLE IF NOT EXISTS utenti
                    (chat_id INTEGER PRIMARY KEY,
                     data_registrazione TEXT)''')
        conn.commit()
        logger.info("Database inizializzato con successo")
    except Exception as e:
        logger.error(f"Errore nell'inizializzazione del database: {str(e)}")
    finally:
        conn.close()

# Modifica la funzione start per registrare gli utenti
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    
    try:
        # Registra l'utente
        conn = get_db_connection()
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""INSERT OR IGNORE INTO utenti (chat_id, data_registrazione) 
                    VALUES (?, ?)""", (user_id, now))
        conn.commit()
        conn.close()
        logger.info(f"Nuovo utente registrato: {user_id}")
        
        keyboard = [['/start', '/lista', '/genera_PDF'],
                    ['/aiuto']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Benvenuto nel Bot di gestione segnalazioni!\n\n"
            "Usa i comandi qui sotto per interagire con il bot.\n"
            "Ogni messaggio che invii verrà registrato come segnalazione.\n\n"
            "Riceverai automaticamente un PDF con le segnalazioni ogni giorno alle 08:00 e alle 20:00.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Errore nella registrazione dell'utente {user_id}: {str(e)}")
        await update.message.reply_text("Si è verificato un errore. Riprova più tardi.")

# Modifica la funzione main
def main():
    logger.info("Avvio del bot...")
    
    # Inizializza il database
    init_db()
    
    # Configura il bot
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("Token non trovato!")
    
    application = ApplicationBuilder().token(token).build()
    
    # Aggiungi gli handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lista", lista))
    application.add_handler(CommandHandler("genera_PDF", genera_PDF))
    application.add_handler(CommandHandler("aiuto", aiuto))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_messaggio))
    
    # Avvia lo scheduler in background
    asyncio.create_task(scheduler_pdf_giornaliero(application))
    
    # Avvia il bot
    logger.info("Bot avviato con successo!")
    
    PORT = int(os.environ.get('PORT', '10000'))
    
    if os.environ.get('RENDER'):
        logger.info(f"Avvio in modalità webhook su porta {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=os.environ.get('WEBHOOK_URL')
        )
    else:
        logger.info("Avvio in modalità polling")
        application.run_polling()

if __name__ == '__main__':
    main()
