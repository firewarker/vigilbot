# [Tutto il codice precedente rimane uguale fino alla funzione main]

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