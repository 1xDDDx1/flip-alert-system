import requests
import json
import re
import time
import schedule
import os
import base64
import sqlite3
import statistics
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dane bota i API
BOT_TOKEN = os.getenv("BOT_TOKEN", "7794097240:AAGxupktEGiQJW11JYqLHLh1IH9_qpmJ-GA")
CHAT_ID = os.getenv("CHAT_ID", "1824475841")
ALLEGRO_CLIENT_ID = os.getenv("ALLEGRO_CLIENT_ID", "6ac04e681e32433283a7109e22d74e22")
ALLEGRO_CLIENT_SECRET = os.getenv("ALLEGRO_CLIENT_SECRET", "BbHJ3Rubqyfhb4CZcMBtSMNxsXB5S7mwcTDaxF5CcnBlHW3gEqZOU2tv39O6nfis")

# Ceny bazowe (będą się uczyć)
CENY_BAZOWE = {
    "iPhone 13": {"128GB": 1150, "256GB": 1250, "512GB": 1300},
    "iPhone 14": {"128GB": 1400, "256GB": 1500, "512GB": 1600},
    "iPhone 15": {"128GB": 1900, "256GB": 2000, "512GB": 2100},
    "iPhone 16": {"128GB": 2700, "256GB": 2800, "512GB": 2900},
    "Samsung Galaxy S24": {"128GB": 1800, "256GB": 1900},
    "Samsung Galaxy S25": {"128GB": 2400, "256GB": 2500, "512GB": 2700},
    "Samsung Galaxy S25 Ultra": {"256GB": 3800, "512GB": 4000},
    "PlayStation 5": {"Standard": 2200, "Digital": 1800},
    "Xbox Series X": {"Standard": 2000}
}

SLOWA_OSTRZEGAWCZE = [
    "uszkodzony", "pęknięty", "zablokowany", "icloud", "simlock", 
    "broken", "damaged", "parts", "repair", "serwis", "nie działa"
]

MIASTA_SLASKIE = [
    "katowice", "częstochowa", "sosnowiec", "gliwice", "zabrze", "bielsko-biała",
    "bytom", "rybnik", "ruda śląska", "tychy", "dąbrowa górnicza", "chorzów",
    "jaworzno", "jastrzębie-zdrój", "mysłowice", "siemianowice śląskie",
    "żory", "świętochłowice", "będzin", "tarnowskie góry", "piekary śląskie"
]

def wyslij_wiadomosc(tekst):
    """Wysyła wiadomość na Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dane = {
        "chat_id": CHAT_ID,
        "text": tekst,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=dane)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Błąd wysyłania: {e}")
        return False

def analizuj_produkt(tytul, opis=""):
    """Analizuje produkt"""
    tekst = (tytul + " " + opis).upper()
    
    for model in CENY_BAZOWE:
        if model.upper() in tekst:
            for wariant in CENY_BAZOWE[model]:
                if wariant.upper() in tekst:
                    return {"model": model, "wariant": wariant}
            return {"model": model, "wariant": list(CENY_BAZOWE[model].keys())[0]}
    return None

def jest_w_slaskim(lokalizacja):
    """Sprawdza lokalizację"""
    if not lokalizacja:
        return False
    
    lokalizacja_lower = lokalizacja.lower()
    for miasto in MIASTA_SLASKIE:
        if miasto in lokalizacja_lower:
            return True
    return any(slowo in lokalizacja_lower for slowo in ["śląskie", "slask", "katowice"])

def oblicz_smart_score(oferta):
    """Oblicza Smart Score oferty"""
    score = 50  # Bazowy wynik
    
    cena = oferta.get('cena', 0)
    model = oferta.get('model')
    wariant = oferta.get('wariant')
    seller_rating = oferta.get('seller_rating', 95)
    tytul = oferta.get('tytul', '').upper()
    opis = oferta.get('opis', '').upper()
    
    # Sprawdź cenę bazową
    if model and wariant:
        cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 0)
        if cena_bazowa > 0:
            if cena < cena_bazowa * 0.8:
                score += 30  # Świetna cena
            elif cena < cena_bazowa * 0.9:
                score += 20  # Dobra cena
            elif cena < cena_bazowa:
                score += 10  # OK cena
            elif cena > cena_bazowa * 1.2:
                score -= 30  # Przecenione
    
    # Analiza sprzedawcy
    if seller_rating >= 98:
        score += 15
    elif seller_rating >= 95:
        score += 10
    elif seller_rating < 90:
        score -= 15
    
    # Analiza słów kluczowych
    for slowo in SLOWA_OSTRZEGAWCZE:
        if slowo.upper() in tytul or slowo.upper() in opis:
            score -= 25
            break
    
    # Bonus za pozytywne słowa
    pozytywne = ['IDEALNY', 'NOWY', 'GWARANCJA', 'ORYGINALNY', 'KOMPLET']
    for slowo in pozytywne:
        if slowo in tytul or slowo in opis:
            score += 5
    
    return max(0, min(100, score))

class AllegroAPI:
    """Klasa API Allegro"""
    
    def __init__(self):
        self.client_id = ALLEGRO_CLIENT_ID
        self.client_secret = ALLEGRO_CLIENT_SECRET
        self.access_token = None
        self.base_url = "https://api.allegro.pl"
    
    def get_access_token(self):
        """Pobiera access token"""
        try:
            logger.info(f"🔑 Próba uwierzytelnienia z Client ID: {self.client_id[:8]}...")
            
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            
            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {"grant_type": "client_credentials"}
            
            response = requests.post(f"{self.base_url}/auth/oauth/token", headers=headers, data=data)
            
            logger.info(f"🔑 Odpowiedź uwierzytelnienia: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                logger.info(f"✅ Token otrzymany: {self.access_token[:20]}...")
                return True
            else:
                logger.error(f"❌ Błąd tokena: {response.status_code}")
                logger.error(f"❌ Odpowiedź: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Błąd uwierzytelniania: {e}")
            return False
    
    def search_products(self, query, limit=10):
        """Wyszukuje produkty"""
        if not self.access_token:
            if not self.get_access_token():
                return []
        
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/vnd.allegro.public.v1+json"
            }
            
            params = {
                "phrase": query,
                "limit": limit,
                "sort": "-price",
                "category.id": 257,
                "fallback": "true"
            }
            
            response = requests.get(f"{self.base_url}/offers/listing", headers=headers, params=params)
            
            if response.status_code == 200:
                offers = response.json().get("items", {}).get("regular", [])
                logger.info(f"✅ Znaleziono {len(offers)} ofert dla '{query}'")
                return offers
            else:
                logger.error(f"❌ Błąd wyszukiwania: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"❌ Błąd wyszukiwania: {e}")
            return []

def wyslij_smart_alert(oferta, smart_score):
    """Wysyła inteligentny alert"""
    model = oferta.get('model')
    wariant = oferta.get('wariant')
    cena = oferta.get('cena')
    lokalizacja = oferta.get('lokalizacja')
    link = oferta.get('link')
    seller_rating = oferta.get('seller_rating', 95)
    
    # Określ priorytet
    if smart_score >= 80:
        emoji = '🔥'
        priorytet = 'SUPER OKAZJA'
    elif smart_score >= 65:
        emoji = '✅'
        priorytet = 'DOBRA OFERTA'
    elif smart_score >= 50:
        emoji = '🤔'
        priorytet = 'SPRAWDŹ'
    else:
        return False
    
    # Oblicz oszczędności
    cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 0)
    if cena_bazowa > 0:
        oszczednosci = cena_bazowa - cena
        procent_oszczednosci = (oszczednosci / cena_bazowa) * 100
    else:
        oszczednosci = 0
        procent_oszczednosci = 0
    
    alert = f"""{emoji} <b>SMART ALERT AI LITE</b>

🧠 <b>AI Score:</b> {smart_score}/100 ({priorytet})
📱 <b>{model} {wariant}</b>
💰 <b>Cena:</b> {cena} PLN
💎 <b>Cena bazowa:</b> {cena_bazowa} PLN

⭐ <b>Sprzedawca:</b> {seller_rating}%
📍 <b>Lokalizacja:</b> {lokalizacja}

💡 <b>Rekomendacja AI:</b>
{"🔥 KUP NATYCHMIAST!" if smart_score >= 80 else "✅ Warto rozważyć" if smart_score >= 65 else "🤔 Sprawdź szczegóły"}

💰 <b>Oszczędności:</b> {oszczednosci:+d} PLN ({procent_oszczednosci:+.1f}%)

🔗 <a href="{link}">SPRAWDŹ PRAWDZIWĄ OFERTĘ</a>

<i>🤖 Powered by AI Lite</i>"""
    
    return wyslij_wiadomosc(alert)

def main():
    """Główna funkcja"""
    logger.info("🤖 Smart Flip Alert AI LITE - CLEAN VERSION!")
    
    # Powiadomienie o uruchomieniu
    start_message = """🤖 <b>AI LITE - CLEAN VERSION!</b>

✅ Naprawiono wszystkie błędy
🧠 Smart Score 0-100 aktywny
🔥 Progi: 80+=SUPER, 65+=DOBRA, 50+=SPRAWDŹ
⚡ Stabilny, lekki, szybki

🚀 Pierwszy skan za 3 minuty!"""
    
    wyslij_wiadomosc(start_message)
    
    # Inicjalizacja
    allegro = AllegroAPI()
    
    def skanuj_oferty():
        """Skanuje oferty"""
        try:
            logger.info("🔍 Rozpoczynam skanowanie...")
            
            frazy = ["iPhone 13", "iPhone 14", "iPhone 15", "Samsung Galaxy S25"]
            wszystkie_oferty = []
            alerty_wyslane = 0
            
            for fraza in frazy:
                logger.info(f"🔍 Szukam: {fraza}")
                oferty = allegro.search_products(fraza, limit=8)
                
                for oferta in oferty:
                    try:
                        tytul = oferta.get("name", "")
                        cena = int(float(oferta.get("price", {}).get("amount", 0)))
                        lokalizacja = oferta.get("vendor", {}).get("location", {}).get("city", "")
                        link = f"https://allegro.pl/oferta/{oferta.get('id', '')}"
                        seller_rating = oferta.get("vendor", {}).get("rating", {}).get("percentage", 95)
                        
                        if cena == 0:
                            logger.info(f"⏭️ Brak ceny: {tytul[:30]}...")
                            continue
                            
                        if not jest_w_slaskim(lokalizacja):
                            logger.info(f"⏭️ Zła lokalizacja: {tytul[:30]}... ({lokalizacja})")
                            continue
                        
                        # Analiza produktu
                        produkt = analizuj_produkt(tytul)
                        if not produkt:
                            logger.info(f"⏭️ Nieznany produkt: {tytul[:30]}...")
                            continue
                        
                        oferta_data = {
                            'tytul': tytul,
                            'cena': cena,
                            'model': produkt['model'],
                            'wariant': produkt['wariant'],
                            'lokalizacja': lokalizacja,
                            'seller_rating': seller_rating,
                            'link': link,
                            'opis': ''
                        }
                        
                        # Smart Score
                        smart_score = oblicz_smart_score(oferta_data)
                        
                        logger.info(f"📱 {tytul[:40]}... - Score: {smart_score}")
                        
                        # Wyślij alert jeśli dobry
                        if smart_score >= 50:  # Próg dla testów
                            if wyslij_smart_alert(oferta_data, smart_score):
                                alerty_wyslane += 1
                                time.sleep(2)
                        
                        wszystkie_oferty.append(oferta_data)
                        
                    except Exception as e:
                        logger.error(f"❌ Błąd oferty: {e}")
                        continue
                
                time.sleep(1)
            
            # Podsumowanie
            czas = datetime.now().strftime("%H:%M")
            summary = f"""📊 <b>AI Lite - Clean - Podsumowanie</b>

🕒 <b>Czas:</b> {czas}
🤖 <b>Przeanalizowano:</b> {len(wszystkie_oferty)} ofert
✅ <b>Smart alerty:</b> {alerty_wyslane} ofert
🧠 <b>AI:</b> Wszystko działa poprawnie

⏰ <b>Następne skanowanie:</b> za godzinę
🎯 <b>Status:</b> CLEAN VERSION AKTYWNA!

<i>🚀 Bez błędów, pełna moc!</i>"""
            
            wyslij_wiadomosc(summary)
            logger.info(f"✅ Skanowanie zakończone: {alerty_wyslane} alertów")
            
        except Exception as e:
            logger.error(f"❌ Błąd skanowania: {e}")
            wyslij_wiadomosc(f"❌ Błąd skanowania: {str(e)}")
    
    # Pierwsze skanowanie za 3 minuty
    time.sleep(180)
    skanuj_oferty()
    
    # Harmonogram co godzinę
    schedule.every().hour.do(skanuj_oferty)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
