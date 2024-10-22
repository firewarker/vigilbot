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

# [Il resto del codice rimane uguale fino alla funzione main]

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
    
    # Gestione per Render
    PORT = int(os.environ.get('PORT', '8080'))
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
    
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
    else:
        application.run_polling()

if __name__ == '__main__':
    main()
