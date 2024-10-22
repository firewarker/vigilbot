import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from fpdf import FPDF
from datetime import datetime, time
from dotenv import load_dotenv

# Carica le variabili di ambiente
load_dotenv()

# Connessione al database SQLite
def get_db_connection():
    conn = sqlite3.connect('segnalazioni.db')
    conn.row_factory = sqlite3.Row
    return conn

# Crea la tabella se non esiste
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS segnalazioni
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 turno TEXT, 
                 segnalazione TEXT,
                 data TEXT)''')
    conn.commit()
    conn.close()

# Funzione per calcolare il turno corrente
def calcola_turno():
    # Data di riferimento
    data_riferimento = datetime(2024, 10, 18)
    oggi = datetime.now()
    
    # Lista dei turni in ordine perpetuo
    turni = ['A', 'B', 'C', 'D']
    
    # Calcola i giorni passati dal giorno di riferimento
    giorni_passati = (oggi - data_riferimento).days
    
    # Ora attuale
    ora_attuale = oggi.time()
    
    # Definisci gli orari per il cambio turno
    orario_diurno_inizio = time(8, 0)
    orario_notturno_inizio = time(20, 0)
    
    # Turno diurno o notturno
    if orario_diurno_inizio <= ora_attuale < orario_notturno_inizio:
        # È turno diurno
        indice_turno = (giorni_passati + 1) % len(turni)
    else:
        # È turno notturno
        indice_turno = giorni_passati % len(turni)
    
    return turni[indice_turno]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['/start', '/lista', '/genera_PDF'],
                ['/aiuto']]
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
        os.remove(file_pdf)  # Rimuove il file dopo l'invio
    except Exception as e:
        await update.message.reply_text(f"❌ Errore nella generazione del PDF: {str(e)}")

def main():
    # Inizializza il database
    init_db()
    
    # Configura il bot
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("❌ Token non trovato! Controlla il file .env")
        
    application = ApplicationBuilder().token(token).build()
    
    # Aggiungi gli handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lista", lista))
    application.add_handler(CommandHandler("genera_PDF", genera_PDF))
    application.add_handler(CommandHandler("aiuto", aiuto))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_messaggio))
    
    # Avvia il bot
    print("🚀 Bot avviato con successo!")
    application.run_polling()

if __name__ == '__main__':
    main()
