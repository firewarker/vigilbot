import os
import sqlite3
import asyncio
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from fpdf import FPDF
from datetime import datetime, time, timezone, timedelta
from dotenv import load_dotenv

# Configura il logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carica le variabili di ambiente
load_dotenv()

def get_tz_italia():
    """
    Restituisce il fuso orario italiano corretto basandosi sulla data
    per gestire automaticamente ora legale/solare
    """
    now = datetime.now()
    # Ora legale in Italia: ultima domenica di marzo - ultima domenica di ottobre
    if 3 <= now.month <= 10:
        return timezone(timedelta(hours=2))  # UTC+2 (ora legale)
    else:
        return timezone(timedelta(hours=1))  # UTC+1 (ora solare)

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
        c.execute('''CREATE TABLE IF NOT EXISTS segnalazioni
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     turno TEXT, 
                     segnalazione TEXT,
                     data TEXT)''')
        # Aggiungi tabella per gli utenti se non esiste
        c.execute('''CREATE TABLE IF NOT EXISTS utenti
                    (chat_id INTEGER PRIMARY KEY)''')
        conn.commit()
        logger.info("Database inizializzato con successo")
    except Exception as e:
        logger.error(f"Errore nell'inizializzazione del database: {e}")
    finally:
        conn.close()

# Funzione per calcolare il turno corrente
def calcola_turno():
    data_riferimento = datetime(2024, 10, 18)
    oggi = datetime.now(get_tz_italia())
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
    chat_id = update.effective_chat.id
    
    # Registra l'utente nel database
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO utenti (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()
    
    keyboard = [['/start', '/lista', '/genera_PDF'],
                ['/ora', '/aiuto']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Benvenuto nel Bot di gestione segnalazioni!\n\n"
        "Usa i comandi qui sotto per interagire con il bot.\n"
        "Ogni messaggio che invii verrà registrato come segnalazione.\n\n"
        "Riceverai automaticamente un PDF alle 8:00 e alle 20:00.",
        reply_markup=reply_markup
    )

async def aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guida = (
        "📋 *Guida del Bot*\n\n"
        "*Comandi disponibili:*\n"
        "• /start - Avvia il bot e mostra il menu principale\n"
        "• /lista - Visualizza le ultime 20 segnalazioni\n"
        "• /genera_PDF - Crea un PDF con tutte le segnalazioni\n"
        "• /ora - Mostra l'ora attuale del bot e il turno\n"
        "• /aiuto - Mostra questo messaggio di aiuto\n\n"
        "*Come funziona:*\n"
        "- Ogni messaggio che invii viene salvato come segnalazione\n"
        "- Il turno viene assegnato automaticamente\n"
        "- Ricevi automaticamente un PDF alle 8:00 e alle 20:00\n"
        "- Puoi generare un PDF manualmente con /genera_PDF"
    )
    await update.message.reply_text(guida, parse_mode='Markdown')

async def gestisci_messaggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo_segnalazione = update.message.text
    chat_id = update.effective_chat.id
    
    try:
        turno = calcola_turno()
        data = datetime.now(get_tz_italia()).strftime("%Y-%m-%d %H:%M:%S")
        
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
    pdf.cell(0, 10, f"Generato il: {datetime.now(get_tz_italia()).strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='L')
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
    
    file_path = f"segnalazioni_{datetime.now(get_tz_italia()).strftime('%Y%m%d_%H%M%S')}.pdf"
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

async def ora_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ora_attuale = datetime.now(get_tz_italia())
    turno_attuale = calcola_turno()
    
    await update.message.reply_text(
        f"🕒 *Informazioni Orario Bot*\n\n"
        f"Data: {ora_attuale.strftime('%d/%m/%Y')}\n"
        f"Ora: {ora_attuale.strftime('%H:%M:%S')}\n"
        f"Fuso Orario: {'Ora Legale (UTC+2)' if ora_attuale.tzinfo.utcoffset(None) == timedelta(hours=2) else 'Ora Solare (UTC+1)'}\n"
        f"Turno Attuale: {turno_attuale}\n\n"
        f"Prossimi invii PDF:\n"
        f"• Mattina: 08:00\n"
        f"• Sera: 20:00",
        parse_mode='Markdown'
    )

async def invia_pdf_programmato(application):
    while True:
        try:
            ora_attuale = datetime.now(get_tz_italia())
            logger.info(f"Controllo orario per invio PDF: {ora_attuale.strftime('%H:%M:%S')}")
            
            # Se l'ora attuale è 08:00 o 20:00
            if ora_attuale.hour in [8, 20] and ora_attuale.minute == 0:
                logger.info("Orario di invio PDF raggiunto")
                try:
                    file_pdf = genera_pdf()
                    logger.info("PDF generato con successo")
                    
                    # Ottieni tutti gli utenti registrati
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT chat_id FROM utenti")
                    utenti = c.fetchall()
                    conn.close()
                    
                    # Invia il PDF a ogni utente
                    for utente in utenti:
                        try:
                            await application.bot.send_document(
                                chat_id=utente['chat_id'],
                                document=open(file_pdf, 'rb'),
                                filename="segnalazioni.pdf",
                                caption=f"📊 Report automatico delle segnalazioni\nGenerato il: {ora_attuale.strftime('%d/%m/%Y %H:%M')}"
                            )
                            logger.info(f"PDF inviato con successo all'utente {utente['chat_id']}")
                            await asyncio.sleep(1)  # Pausa tra gli invii
                        except Exception as e:
                            logger.error(f"Errore nell'invio del PDF all'utente {utente['chat_id']}: {e}")
                    
                    os.remove(file_pdf)
                    await asyncio.sleep(60)  # Attendi un minuto per evitare invii duplicati
                except Exception as e:
                    logger.error(f"Errore nella generazione/invio del PDF: {e}")
            
            # Attendi 30 secondi prima del prossimo controllo
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Errore nel loop di controllo: {e}")
            await asyncio.sleep(60)

async def main_async():
    logger.info("Inizializzazione del bot...")
    
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
    application.add_handler(CommandHandler("ora", ora_bot))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_messaggio))
    
    # Avvia lo scheduler in background
    asyncio.create_task(invia_pdf_programmato(application))
    
    # Avvia il bot
    logger.info(f"Bot avviato con successo! Ora corrente: {datetime.now(get_tz_italia()).strftime('%H:%M:%S')}")
    
    PORT = int(os.environ.get('PORT', '10000'))
    
    if os.environ.get('RENDER'):
        logger.info(f"Avvio in modalità webhook su porta {PORT}")
        await application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=os.environ.get('WEBHOOK_URL')
        )
    else:
        logger.info("Avvio in modalità polling")
        await application.run_polling()

def main():
    asyncio.run(main_async())

if __name__ == '__main__':
    main()