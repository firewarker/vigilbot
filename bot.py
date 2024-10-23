import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from fpdf import FPDF
from datetime import datetime, time, timezone, timedelta
from dotenv import load_dotenv

# Carica le variabili di ambiente
load_dotenv()

def get_tz_italia():
    """
    Restituisce il fuso orario italiano corretto basandosi sulla data
    per gestire automaticamente ora legale/solare
    """
    now = datetime.now()
    
    def is_dst(dt):
        # Ultima domenica di marzo
        dst_start = datetime(dt.year, 3, 31)
        while dst_start.weekday() != 6:  # 6 = domenica
            dst_start -= timedelta(days=1)
        
        # Ultima domenica di ottobre
        dst_end = datetime(dt.year, 10, 31)
        while dst_end.weekday() != 6:  # 6 = domenica
            dst_end -= timedelta(days=1)
        
        return dst_start <= dt.replace(tzinfo=None) <= dst_end
    
    return timezone(timedelta(hours=2 if is_dst(now) else 1))

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
        conn.commit()
    except Exception as e:
        print(f"Errore nell'inizializzazione del database: {e}")
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
    keyboard = [['/start', '/lista', '/genera_PDF'],
                ['/ora', '/aiuto']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Benvenuto nel Bot di gestione segnalazioni!\n\n"
        "Usa i comandi qui sotto per interagire con il bot.\n"
        "Ogni messaggio che invii verrà registrato come segnalazione.",
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
        "- Puoi visualizzare le segnalazioni con /lista\n"
        "- Puoi generare un report PDF completo con /genera_PDF"
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
    ora_generazione = datetime.now(get_tz_italia()).strftime("%d/%m/%Y %H:%M:%S")
    pdf.cell(0, 10, f"Generato il: {ora_generazione}", ln=True, align='L')
    pdf.ln(10)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Prima ottieni il numero totale di segnalazioni
    c.execute("SELECT COUNT(*) as total FROM segnalazioni")
    total = c.fetchone()['total']
    
    # Poi ottieni tutte le segnalazioni ordinate per data
    c.execute("SELECT * FROM segnalazioni ORDER BY data DESC")
    segnalazioni = c.fetchall()
    conn.close()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Elenco Completo Segnalazioni (Totale: {total})", ln=True)
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
            filename=f"segnalazioni_complete_{datetime.now(get_tz_italia()).strftime('%Y%m%d_%H%M')}.pdf",
            caption="📊 Report completo di tutte le segnalazioni"
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
        f"Turno Attuale: {turno_attuale}",
        parse_mode='Markdown'
    )

def main():
    print("Inizializzazione del bot...")
    
    # Inizializza il database
    try:
        print("Inizializzazione database...")
        init_db()
        print("Database inizializzato con successo!")
    except Exception as e:
        print(f"Errore nell'inizializzazione del database: {e}")
    
    # Configura il bot
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("❌ Token non trovato! Controlla il file .env")
    
    # Crea l'applicazione
    application = ApplicationBuilder().token(token).build()
    
    # Aggiungi gli handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lista", lista))
    application.add_handler(CommandHandler("genera_PDF", genera_PDF))
    application.add_handler(CommandHandler("aiuto", aiuto))
    application.add_handler(CommandHandler("ora", ora_bot))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_messaggio))
    
    # Avvia il bot
    print("🚀 Bot avviato con successo!")
    print(f"Ora corrente del bot: {datetime.now(get_tz_italia()).strftime('%H:%M:%S')}")
    
    # Gestione webhook per Render
    PORT = int(os.environ.get('PORT', '10000'))
    
    if os.environ.get('RENDER'):
        print(f"Avvio in modalità webhook su porta {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=os.environ.get('WEBHOOK_URL')
        )
    else:
        print("Avvio in modalità polling")
        application.run_polling()

if __name__ == '__main__':
    main()