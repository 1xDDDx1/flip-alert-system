import requests
import time
import os
import schedule
import logging

# Konfiguracja
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dane - hardcoded żeby na pewno działało
BOT_TOKEN = "7794097240:AAGxupktEGiQJW11JYqLHLh1IH9_qpmJ-GA"
CHAT_ID = "1824475841"

def wyslij_wiadomosc(tekst):
    """Wysyła wiadomość na Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        dane = {
            "chat_id": CHAT_ID,
            "text": tekst,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=dane)
        if response.status_code == 200:
            logger.info("✅ Wiadomość wysłana")
            return True
        else:
            logger.error(f"❌ Błąd: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Błąd wysyłania: {e}")
        return False

def test_systemu():
    """Test podstawowej funkcjonalności"""
    try:
        logger.info("🧪 Testowanie systemu...")
        
        # Test 1: Telegram
        if wyslij_wiadomosc("🧪 Test systemu - Telegram działa!"):
            logger.info("✅ Test Telegram: PASS")
        else:
            logger.error("❌ Test Telegram: FAIL")
            return False
        
        # Test 2: Zmienne środowiskowe
        bot_token_env = os.getenv("BOT_TOKEN")
        chat_id_env = os.getenv("CHAT_ID")
        
        if bot_token_env and chat_id_env:
            logger.info("✅ Test zmiennych: PASS")
            wyslij_wiadomosc("✅ Zmienne środowiskowe działają!")
        else:
            logger.warning("⚠️ Zmienne środowiskowe nie znalezione, używam hardcoded")
            wyslij_wiadomosc("⚠️ Używam hardcoded danych (to OK)")
        
        # Test 3: Requests
        test_response = requests.get("https://httpbin.org/status/200")
        if test_response.status_code == 200:
            logger.info("✅ Test requests: PASS")
            wyslij_wiadomosc("✅ Połączenie internetowe działa!")
        else:
            logger.error("❌ Test requests: FAIL")
            return False
        
        wyslij_wiadomosc("🎉 Wszystkie testy przeszły pomyślnie!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Błąd testu: {e}")
        wyslij_wiadomosc(f"❌ Błąd testu: {str(e)}")
        return False

def prosty_skan():
    """Bardzo prosty skan bez API"""
    try:
        logger.info("🔍 Prosty skan...")
        
        # Symulowane oferty dla testów
        oferty = [
            {"nazwa": "iPhone 13 128GB", "cena": 950, "score": 85},
            {"nazwa": "Samsung Galaxy S25 256GB", "cena": 2300, "score": 72},
            {"nazwa": "PlayStation 5", "cena": 1900, "score": 78}
        ]
        
        dobre_oferty = [o for o in oferty if o["score"] >= 70]
        
        if dobre_oferty:
            alert = "🔥 <b>PROSTY SKAN - DOBRE OFERTY!</b>\n\n"
            
            for oferta in dobre_oferty:
                emoji = "🔥" if oferta["score"] >= 80 else "✅"
                alert += f"{emoji} {oferta['nazwa']}\n"
                alert += f"💰 {oferta['cena']} PLN (Score: {oferta['score']}/100)\n\n"
            
            alert += "<i>🧪 To test - za moment prawdziwe API!</i>"
            
            wyslij_wiadomosc(alert)
            logger.info(f"✅ Wysłano {len(dobre_oferty)} alertów")
        else:
            wyslij_wiadomosc("😔 Brak dobrych ofert w teście")
            logger.info("ℹ️ Brak dobrych ofert")
        
        # Podsumowanie
        wyslij_wiadomosc(f"""📊 <b>Prosty skan zakończony</b>

🔍 Przeanalizowano: {len(oferty)} ofert
✅ Dobre oferty: {len(dobre_oferty)}
⏰ Następny skan: za godzinę

🎯 Status: SYSTEM DZIAŁA!""")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Błąd skanu: {e}")
        wyslij_wiadomosc(f"❌ Błąd skanu: {str(e)}")
        return False

def main():
    """Główna funkcja - ultra prosta"""
    try:
        logger.info("🚀 ULTRA SIMPLE AI - START!")
        
        # Powiadomienie o starcie
        wyslij_wiadomosc("""🚀 <b>ULTRA SIMPLE AI</b>

✅ Najprostszy możliwy system
🧪 Testowanie podstawowych funkcji
🔍 Za 2 minuty pierwszy prosty skan

⚡ Jeśli to działa - dodamy Allegro API!""")
        
        # Test systemu
        if not test_systemu():
            logger.error("❌ Testy nie przeszły!")
            return
        
        # Pierwszy skan za 2 minuty
        logger.info("⏰ Pierwszy skan za 2 minuty...")
        time.sleep(120)
        
        # Wykonaj pierwszy skan
        prosty_skan()
        
        # Harmonogram co godzinę
        schedule.every().hour.do(prosty_skan)
        
        logger.info("🔄 Harmonogram uruchomiony - skan co godzinę")
        
        # Główna pętla
        while True:
            schedule.run_pending()
            time.sleep(60)
            
    except Exception as e:
        logger.error(f"❌ Krytyczny błąd: {e}")
        wyslij_wiadomosc(f"❌ ULTRA SIMPLE AI - Błąd: {str(e)}")

if __name__ == "__main__":
    main()
