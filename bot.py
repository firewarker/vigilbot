import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from fpdf import FPDF
from datetime import datetime, time, timedelta
from dotenv import load_dotenv
import logging
import asyncio

# Carica le variabili di ambiente
load_dotenv()

# Configura il logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Connessione al database SQLite
def get_db_connection():
    conn = sqlite3.connect('segnalazioni.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Crea la tabella se non esiste
def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
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
        logger.error(f"Errore nell'inizializzazione del database: {e}")
    finally:
        conn.close()

# Funzione per calcolare il turno corrente
def calcola_turno():
    data_riferimento = datetime(2024, 10, 18)
    oggi = datetime.now()
    turni = ['A', 'B', 'C', 'D']
    giorni_passati = (oggi - data_riferimento).days
    ora_attuale = oggi.time()
    orario_diurno_inizio = time(8, 0)
    orario_notturno_inizio = time(20, 0)
    
    if orario_diurno_inizio <= ora_attuale < orario_notturno_inizio:
        indice_turno = (giorni_passati + 1) % len(turni)
    else:
        indice_turno = giorni_passati % len(turni)
    
    return turni[indice_turno]

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

async def aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guida = (
        "📋 *Guida del Bot*\n\n"
        "*Comandi disponibili:*\n"
        "• /start - Avvia il bot e mostra il menu principale\n"
        "• /lista - Visualizza le ultime 20 segnalazioni\n"
        "• /genera_PDF - Crea un PDF con tutte le segnalazioni\n"
        "• /aiuto - Mostra questo messaggio di aiuto\n\n"
        "*Come funziona:*\n"
        "- Ogni messaggio che invii viene salvato come segnalazione\n"
        "- Il turno viene assegnato automaticamente\n"
        "- Puoi visualizzare le segnalazioni con /lista\n"
        "- Puoi generare un report PDF con /genera_PDF"
    )
    await update.message.reply_text(guida, parse_mode='Markdown')

async def gestisci_messaggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo_segnalazione = update.message.text
    
    try:
        turno = calcola_turno()
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO segnalazioni (turno, segnalazione, data) VALUES (?, ?, ?)",
                 (turno, testo_segnalazione, data))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Segnalazione registrata!\n"
            f"📝 Turno: {turno}\n"
            f"🕒 Data: {data}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM segnalazioni ORDER BY data DESC LIMIT 20")
    segnalazioni = c.fetchall()
    conn.close()
    
    if segnalazioni:
        risposta = "*📋 Ultime 20 segnalazioni:*\n\n" + "\n\n".join(
            f"🔸 *Turno {row['turno']}*\n"
            f"📝 {row['segnalazione']}\n"
            f"🕒 {row['data']}"
            for row in segnalazioni
        )
        await update.message.reply_text(risposta, parse_mode='Markdown')
    else:
        await update.message.reply_text("📝 Non ci sono segnalazioni registrate.")

def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Registro Segnalazioni", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='L')
    pdf.ln(10)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM segnalazioni ORDER BY data DESC")
    segnalazioni = c.fetchall()
    conn.close()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Elenco Segnalazioni:", ln=True)
    pdf.ln(5)
    
    for segnalazione in segnalazioni:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, f"Turno {segnalazione['turno']} - {segnalazione['data']}", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 7, segnalazione['segnalazione'])
        pdf.ln(5)
    
    file_path = f"segnalazioni_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(file_path)
    return file_path

async def genera_PDF(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Generazione PDF in corso...")
    try:
        file_pdf = genera_pdf()
        await update.message.reply_document(
            document=open(file_pdf, 'rb'),
            filename="segnalazioni.pdf",
            caption="📊 Ecco il report delle segnalazioni in formato PDF"
        )
        os.remove(file_pdf)
    except Exception as e:
        await update.message.reply_text(f"❌ Errore nella generazione del PDF: {str(e)}")

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
