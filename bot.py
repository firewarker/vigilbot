import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from fpdf import FPDF
from datetime import datetime, time, timezone, timedelta
from dotenv import load_dotenv
import asyncio
import logging

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

def get_db_connection():
    conn = sqlite3.connect('segnalazioni.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS segnalazioni
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     turno TEXT, 
                     segnalazione TEXT,
                     data TEXT)''')
        conn.commit()
    except Exception as e:
        logger.error(f"Errore nell'inizializzazione del database: {e}")
    finally:
        conn.close()

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['/start', '/lista', '/genera_PDF'],
                ['/ora', '/aiuto']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Benvenuto nel Bot di gestione segnalazioni!\n\n"
        "Usa i comandi qui sotto per interagire con il bot.\n"
        "Ogni messaggio che invii verrà registrato come segnalazione.\n\n"
        "Il bot genererà automaticamente un PDF alle 8:00 e alle 20:00.",
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
        "- Alle 8:00 e alle 20:00 viene generato automaticamente un PDF\n"
        "- Puoi generare un PDF manualmente con /genera_PDF"
    )
    await update.message.reply_text(guida, parse_mode='Markdown')

async def gestisci_messaggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo_segnalazione = update.message.text
    
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

async def invia_pdf_programmato(application):
    while True:
        try:
            ora_attuale = datetime.now(get_tz_italia())
            
            # Imposta gli orari di invio
            orari_invio = [
                time(8, 0),   # 08:00
                time(20, 0)   # 20:00
            ]
            
            # Trova il prossimo orario di invio
            prossimo_invio = None
            for orario in orari_invio:
                target = ora_attuale.replace(hour=orario.hour, minute=orario.minute, second=0, microsecond=0)
                if target <= ora_attuale:
                    target += timedelta(days=1)
                if prossimo_invio is None or target < prossimo_invio:
                    prossimo_invio = target

            # Calcola i secondi di attesa
            seconds_to_wait = (prossimo_invio - ora_attuale).total_seconds()
            logger.info(f"Prossimo invio PDF programmato per: {prossimo_invio}")
            
            await asyncio.sleep(seconds_to_wait)
            
            # Genera e invia il PDF
            try:
                file_pdf = genera_pdf()
                
                # Ottieni tutti gli utenti dal database
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT DISTINCT chat_id FROM segnalazioni")
                utenti = c.fetchall()
                conn.close()
                
                # Invia il PDF a tutti gli utenti
                for utente in utenti:
                    try:
                        chat_id = utente[0]
                        await application.bot.send_document(
                            chat_id=chat_id,
                            document=open(file_pdf, 'rb'),
                            filename=f"segnalazioni_{ora_attuale.strftime('%Y%m%d_%H%M')}.pdf",
                            caption=f"📊 Report automatico delle segnalazioni\nGenerato il: {ora_attuale.strftime('%d/%m/%Y %H:%M')}"
                        )
                        logger.info(f"PDF inviato con successo a {chat_id}")
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Errore nell'invio del PDF all'utente {chat_id}: {e}")
                
                os.remove(file_pdf)
                
            except Exception as e:
                logger.error(f"Errore nella generazione/invio del PDF: {e}")
            
        except Exception as e:
            logger.error(f"Errore nello scheduler: {e}")
            await asyncio.sleep(60)

def main():
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
