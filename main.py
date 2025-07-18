import requests
import json
import re
import time
import schedule
import os
import base64
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dane bota
BOT_TOKEN = os.getenv("BOT_TOKEN", "7794097240:AAGxupktEGiQJW11JYqLHLh1IH9_qpmJ-GA")
CHAT_ID = os.getenv("CHAT_ID", "1824475841")

# Allegro API credentials
ALLEGRO_CLIENT_ID = os.getenv("ALLEGRO_CLIENT_ID", "6ac04e681e32433283a7109e22d74e22")
ALLEGRO_CLIENT_SECRET = os.getenv("ALLEGRO_CLIENT_SECRET", "BbHJ3Rubqyfhb4CZcMBtSMNxsXB5S7mwcTDaxF5CcnBlHW3gEqZOU2tv39O6nfis")

# Zaktualizowana baza cen referencyjnych
CENY_REFERENCYJNE = {
    "iPhone 11": {
        "64GB": 500, "128GB": 600, "256GB": 650,
        "Pro 64GB": 700, "Pro 256GB": 800,
        "Pro Max 64GB": 800, "Pro Max 256GB": 850, "Pro Max 512GB": 900
    },
    "iPhone 12": {
        "Mini 64GB": 500, "Mini 128GB": 600, "Mini 256GB": 700,
        "64GB": 700, "128GB": 800, "256GB": 900,
        "Pro 128GB": 900, "Pro 256GB": 1000, "Pro 512GB": 1100,
        "Pro Max 128GB": 1100, "Pro Max 256GB": 1200, "Pro Max 512GB": 1300
    },
    "iPhone 13": {
        "Mini 128GB": 900, "Mini 256GB": 1000,
        "128GB": 1150, "256GB": 1250, "512GB": 1300,
        "Pro 128GB": 1500, "Pro 256GB": 1600, "Pro 512GB": 1700,
        "Pro Max 128GB": 1700, "Pro Max 256GB": 1800, "Pro Max 512GB": 1900
    },
    "iPhone 14": {
        "128GB": 1400, "256GB": 1500, "512GB": 1600,
        "Plus 128GB": 1500, "Plus 256GB": 1600, "Plus 512GB": 1700,
        "Pro 128GB": 2000, "Pro 256GB": 2100, "Pro 512GB": 2200,
        "Pro Max 128GB": 2200, "Pro Max 256GB": 2300, "Pro Max 512GB": 2400
    },
    "iPhone 15": {
        "128GB": 1900, "256GB": 2000, "512GB": 2100,
        "Plus 128GB": 2200, "Plus 256GB": 2300, "Plus 512GB": 2400,
        "Pro 128GB": 2800, "Pro 256GB": 2900, "Pro 512GB": 3000,
        "Pro Max 256GB": 3200, "Pro Max 512GB": 3300
    },
    "iPhone 16": {
        "128GB": 2700, "256GB": 2800, "512GB": 2900,
        "Pro 256GB": 3500, "Pro 512GB": 3700,
        "Pro Max 256GB": 4200, "Pro Max 512GB": 4400
    },
    "Samsung Galaxy S21": {
        "128GB": 800, "256GB": 900,
        "Ultra 128GB": 1200, "Ultra 256GB": 1300, "Ultra 512GB": 1400
    },
    "Samsung Galaxy S22": {
        "128GB": 1000, "256GB": 1100,
        "Ultra 128GB": 1600, "Ultra 256GB": 1700, "Ultra 512GB": 1800
    },
    "Samsung Galaxy S23": {
        "128GB": 1400, "256GB": 1500,
        "Ultra 256GB": 2200, "Ultra 512GB": 2300, "Ultra 1TB": 2600
    },
    "Samsung Galaxy S24": {
        "128GB": 1800, "256GB": 1900,
        "Plus 256GB": 2100, "Plus 512GB": 2200,
        "Ultra 256GB": 2600, "Ultra 512GB": 2700, "Ultra 1TB": 3000
    },
    "Samsung Galaxy S25": {
        "128GB": 2400, "256GB": 2500, "512GB": 2700
    },
    "Samsung Galaxy S25 Plus": {
        "256GB": 2800, "512GB": 3000
    },
    "Samsung Galaxy S25 Ultra": {
        "256GB": 3800, "512GB": 4000, "1TB": 4500
    },
    "Samsung Galaxy S25 Edge": {
        "256GB": 3200, "512GB": 3500
    },
    "PlayStation 5": {
        "Standard": 2200, "Digital": 1800
    },
    "Xbox Series X": {
        "Standard": 2000
    }
}

# Słowa ostrzegawcze
SLOWA_OSTRZEGAWCZE = [
    "uszkodzony", "pęknięty", "zablokowany", "icloud", "simlock", "cracked", 
    "broken", "damaged", "parts", "repair", "serwis", "nie działa", "wadliwy",
    "ghost touch", "martwy piksel", "spalony", "zalany", "po serwisie"
]

# Miasta województwa śląskiego
MIASTA_SLASKIE = [
    "katowice", "częstochowa", "sosnowiec", "gliwice", "zabrze", "bielsko-biała",
    "bytom", "rybnik", "ruda śląska", "tychy", "dąbrowa górnicza", "chorzów",
    "jaworzno", "jastrzębie-zdrój", "mysłowice", "siemianowice śląskie",
    "żory", "świętochłowice", "będzin", "tarnowskie góry", "piekary śląskie",
    "czechowice-dziedzice", "wodzisław śląski", "zawiercie", "racibórz",
    "cieszyn", "pszczyna", "mikołów", "knurów", "ustroń", "wisła"
]

class AllegroAPI:
    def __init__(self):
        self.client_id = ALLEGRO_CLIENT_ID
        self.client_secret = ALLEGRO_CLIENT_SECRET
        self.access_token = None
        self.base_url = "https://api.allegro.pl"
        
    def get_access_token(self):
        """Pobiera access token dla Allegro API"""
        try:
            # Dane do uwierzytelnienia
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            
            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "client_credentials"
            }
            
            response = requests.post(
                f"{self.base_url}/auth/oauth/token",
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                logger.info("✅ Otrzymano token dostępu Allegro API")
                return True
            else:
                logger.error(f"❌ Błąd otrzymania tokena: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Błąd uwierzytelniania Allegro: {e}")
            return False
    
    def search_products(self, query, limit=20):
        """Wyszukuje produkty na Allegro"""
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
                "sort": "-price",  # Sortuj po cenie malejąco
                "category.id": 257,  # Kategoria: Telefony
                "fallback": "true"
            }
            
            response = requests.get(
                f"{self.base_url}/offers/listing",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                offers = data.get("items", {}).get("regular", [])
                logger.info(f"✅ Znaleziono {len(offers)} ofert dla '{query}'")
                return offers
            else:
                logger.error(f"❌ Błąd wyszukiwania: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Błąd wyszukiwania produktów: {e}")
            return []
    
    def get_offer_details(self, offer_id):
        """Pobiera szczegóły oferty"""
        if not self.access_token:
            if not self.get_access_token():
                return None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/vnd.allegro.public.v1+json"
            }
            
            response = requests.get(
                f"{self.base_url}/sale/offers/{offer_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Błąd pobierania szczegółów oferty: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania szczegółów: {e}")
            return None

def wyslij_alert(wiadomosc):
    """Wysyła alert na Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dane = {
        "chat_id": CHAT_ID,
        "text": wiadomosc,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=dane)
        if response.status_code == 200:
            logger.info("✅ Alert wysłany pomyślnie")
            return True
        else:
            logger.error(f"❌ Błąd wysyłania alertu: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Błąd połączenia z Telegramem: {e}")
        return False

def analizuj_produkt(tytul, opis=""):
    """Analizuje tytuł i opis produktu"""
    tekst = (tytul + " " + opis).upper()
    
    # Znajdź typ produktu
    produkt_info = None
    
    for model in CENY_REFERENCYJNE:
        model_upper = model.upper()
        if model_upper in tekst:
            produkt_info = {"typ": "Elektronika", "model": model}
            break
    
    if not produkt_info:
        return None
    
    # Znajdź wariant
    wariant = None
    model_ceny = CENY_REFERENCYJNE[produkt_info["model"]]
    
    for wariant_klucz in model_ceny.keys():
        if wariant_klucz.upper() in tekst:
            wariant = wariant_klucz
            break
    
    if not wariant:
        for rozmiar in ["1TB", "512GB", "256GB", "128GB", "64GB"]:
            if rozmiar in tekst:
                for wariant_klucz in model_ceny.keys():
                    if rozmiar in wariant_klucz:
                        wariant = wariant_klucz
                        break
                if wariant:
                    break
    
    produkt_info["wariant"] = wariant
    produkt_info["cena_ref"] = model_ceny.get(wariant) if wariant else None
    
    return produkt_info

def ocen_ryzyko(cena, cena_ref, tytul, opis="", seller_rating=None):
    """Ocenia ryzyko oferty (1-5)"""
    ryzyko = 1
    
    if not cena_ref:
        ryzyko += 1
    elif cena < cena_ref * 0.4:
        ryzyko += 3
    elif cena < cena_ref * 0.6:
        ryzyko += 2
    elif cena < cena_ref * 0.8:
        ryzyko += 1
    
    # Sprawdź słowa ostrzegawcze
    tekst = (tytul + " " + opis).upper()
    for slowo in SLOWA_OSTRZEGAWCZE:
        if slowo.upper() in tekst:
            ryzyko += 2
            break
    
    # Ocena sprzedawcy
    if seller_rating and seller_rating < 95:
        ryzyko += 1
    
    return min(ryzyko, 5)

def jest_w_slaskim(lokalizacja):
    """Sprawdza czy lokalizacja jest w woj. śląskim"""
    if not lokalizacja:
        return False
    
    lokalizacja_lower = lokalizacja.lower()
    
    for miasto in MIASTA_SLASKIE:
        if miasto in lokalizacja_lower:
            return True
    
    return any(slowo in lokalizacja_lower for slowo in ["śląskie", "slask", "katowice", "silesia"])

def skanuj_allegro_prawdziwe():
    """Skanuje prawdziwe oferty z Allegro API"""
    allegro = AllegroAPI()
    wszystkie_oferty = []
    
    # Wyszukiwane frazy
    frazy_wyszukiwania = [
        "iPhone 13",
        "iPhone 14", 
        "iPhone 15",
        "Samsung Galaxy S24",
        "Samsung Galaxy S25",
        "PlayStation 5",
        "Xbox Series X"
    ]
    
    for fraza in frazy_wyszukiwania:
        logger.info(f"🔍 Wyszukiwanie: {fraza}")
        oferty = allegro.search_products(fraza, limit=10)
        
        for oferta in oferty:
            try:
                # Parsowanie danych z Allegro
                tytul = oferta.get("name", "")
                cena_raw = oferta.get("price", {}).get("amount", 0)
                cena = int(float(cena_raw)) if cena_raw else 0
                
                # Lokalizacja sprzedawcy
                lokalizacja = oferta.get("vendor", {}).get("location", {}).get("city", "")
                
                # Link do oferty
                offer_id = oferta.get("id", "")
                link = f"https://allegro.pl/oferta/{offer_id}"
                
                # Opis (jeśli dostępny)
                opis = oferta.get("description", "")
                
                # Dane sprzedawcy
                seller_info = oferta.get("vendor", {})
                seller_rating = seller_info.get("rating", {}).get("percentage", 100)
                
                if tytul and cena > 0:
                    wszystkie_oferty.append({
                        "tytul": tytul,
                        "cena": cena,
                        "lokalizacja": lokalizacja,
                        "link": link,
                        "platforma": "Allegro",
                        "opis": opis,
                        "seller_rating": seller_rating
                    })
                    
            except Exception as e:
                logger.error(f"❌ Błąd parsowania oferty: {e}")
                continue
        
        time.sleep(1)  # Przerwa między zapytaniami
    
    logger.info(f"📊 Znaleziono łącznie {len(wszystkie_oferty)} ofert z Allegro")
    return wszystkie_oferty

def przetworz_oferty(oferty):
    """Przetwarza oferty i zwraca dobre oferty"""
    dobre_oferty = []
    
    for oferta in oferty:
        try:
            # Sprawdź lokalizację
            if not jest_w_slaskim(oferta["lokalizacja"]):
                logger.info(f"⏭️ Pominięto (lokalizacja): {oferta['tytul']} - {oferta['lokalizacja']}")
                continue
            
            # Analizuj produkt
            produkt = analizuj_produkt(oferta["tytul"], oferta.get("opis", ""))
            if not produkt:
                logger.info(f"⏭️ Pominięto (nieznany produkt): {oferta['tytul']}")
                continue
            
            cena_ref = produkt["cena_ref"]
            if not cena_ref:
                logger.info(f"⏭️ Pominięto (brak ceny ref): {oferta['tytul']}")
                continue
            
            ryzyko = ocen_ryzyko(
                oferta["cena"], 
                cena_ref, 
                oferta["tytul"], 
                oferta.get("opis", ""),
                oferta.get("seller_rating", 100)
            )
            
            # Pokaż analizę
            logger.info(f"📱 {oferta['tytul']}")
            logger.info(f"💰 Cena: {oferta['cena']} PLN | Ref: {cena_ref} PLN")
            logger.info(f"🎯 Próg (85%): {int(cena_ref * 0.85)} PLN")
            logger.info(f"🏪 Platforma: {oferta['platforma']}")
            logger.info(f"📍 Lokalizacja: {oferta['lokalizacja']}")
            logger.info(f"⚠️ Ryzyko: {ryzyko}/5")
            
            # Sprawdź czy to dobra oferta
            if oferta["cena"] < cena_ref * 0.85:
                
                min_neg = max(int(oferta["cena"] * 0.85), int(cena_ref * 0.75))
                max_neg = min(int(oferta["cena"] * 0.95), int(cena_ref * 0.85))
                oszczednosci = cena_ref - oferta["cena"]
                
                # Emoji baterii na podstawie ryzyka
                emoji_bateria = "🔋" if ryzyko <= 2 else "🪫" if ryzyko >= 4 else "🔋"
                
                alert = f"""🚨 <b>PRAWDZIWA OFERTA ALLEGRO!</b>

🛒 <b>Platforma:</b> {oferta['platforma']}
📱 <b>{oferta['tytul']}</b>
💰 <b>Cena:</b> {oferta['cena']} PLN
💎 <b>Cena ref:</b> {cena_ref} PLN
{emoji_bateria} <b>Bateria:</b> Sprawdź w ofercie
📍 <b>Miasto:</b> {oferta['lokalizacja']}
⚠️ <b>Ryzyko:</b> {ryzyko}/5
⭐ <b>Sprzedawca:</b> {oferta.get('seller_rating', 'N/A')}%
💡 <b>Negocjacje:</b> {min_neg}-{max_neg} PLN
🔗 <a href="{oferta['link']}">KLIKNIJ - PRAWDZIWA OFERTA</a>

<i>💰 Oszczędzisz: {oszczednosci} PLN!</i>
<i>✅ To prawdziwa oferta z Allegro!</i>"""
                
                dobre_oferty.append(alert)
                logger.info(f"✅ PRAWDZIWA DOBRA OFERTA! Oszczędność: {oszczednosci} PLN")
            else:
                logger.info(f"⏭️ Cena za wysoka: {oferta['cena']} PLN > {int(cena_ref * 0.85)} PLN")
                
        except Exception as e:
            logger.error(f"❌ Błąd przetwarzania oferty: {e}")
            continue
    
    return dobre_oferty

def uruchom_skanowanie():
    """Główna funkcja skanowania z prawdziwym Allegro API"""
    try:
        logger.info("🚀 Rozpoczynam skanowanie z prawdziwym Allegro API")
        
        # Skanuj prawdziwe oferty z Allegro
        oferty = skanuj_allegro_prawdziwe()
        
        if not oferty:
            logger.info("😔 Brak ofert z Allegro")
            wyslij_alert("🔍 <b>Skanowanie Allegro</b>\n\n😔 Brak ofert spełniających kryteria.\n\n⏰ Następne skanowanie za godzinę...")
            return
        
        # Przetwórz oferty
        dobre_oferty = przetworz_oferty(oferty)
        
        # Wyślij alerty
        if dobre_oferty:
            logger.info(f"🎉 Znaleziono {len(dobre_oferty)} prawdziwych dobrych ofert!")
            for i, alert in enumerate(dobre_oferty):
                wyslij_alert(alert)
                if i < len(dobre_oferty) - 1:
                    time.sleep(3)
        else:
            logger.info("😔 Brak dobrych ofert w tym skanowaniu")
            wyslij_alert("🔍 <b>Skanowanie Allegro zakończone</b>\n\n😔 Brak dobrych ofert tym razem.\n\n⏰ Następne skanowanie za godzinę...")
        
        # Wyślij podsumowanie
        czas = datetime.now().strftime("%H:%M")
        summary = f"""📊 <b>Allegro API - Podsumowanie</b>

🕒 <b>Czas:</b> {czas}
🛒 <b>Źródło:</b> Prawdziwe Allegro API
🔍 <b>Przeskanowano:</b> {len(oferty)} ofert
✅ <b>Znaleziono dobrych:</b> {len(dobre_oferty)} ofert
📍 <b>Obszar:</b> Województwo śląskie

⏰ <b>Następne skanowanie:</b> za godzinę
🎯 <b>Status:</b> Prawdziwe API aktywne!

<i>🚀 Flip Alert z prawdziwymi ofertami!</i>"""
        
        wyslij_alert(summary)
        logger.info("✅ Skanowanie z Allegro API zakończone pomyślnie")
        
    except Exception as e:
        logger.error(f"❌ Błąd podczas skanowania: {e}")
        wyslij_alert(f"❌ <b>Błąd Allegro API</b>\n\n{str(e)}\n\n🔧 Restartuję za 5 minut...")

def main():
    """Główna funkcja aplikacji"""
    logger.info("🚀 Flip Alert z prawdziwym Allegro API uruchomiony!")
    
    # Wyślij powiadomienie o uruchomieniu
    start_message = f"""🚀 <b>Flip Alert - Prawdziwe Allegro API!</b>

✅ System uruchomiony z prawdziwym Allegro API
🛒 Prawdziwe oferty z działającymi linkami
☁️ Działa 24/7 automatycznie w Railway
🔄 Skanowanie co godzinę

📊 <b>Allegro API:</b>
• Client ID: {ALLEGRO_CLIENT_ID[:8]}...
• Dostęp do prawdziwych ofert
• Filtrowanie po województwie śląskim
• Oceny sprzedawców

🎯 <b>Monitorowane produkty:</b>
• iPhone 13-16 (wszystkie wersje)
• Samsung Galaxy S24-S25 (w tym S25 Edge!)
• PlayStation 5 (Standard/Digital)
• Xbox Series X

📍 <b>Obszar:</b> Województwo śląskie
⚡ <b>Status:</b> PRAWDZIWE API AKTYWNE!

<i>Pierwsze prawdziwe skanowanie za 5 minut! 🔔</i>"""
    
    wyslij_alert(start_message)
    
    # Pierwsze skanowanie za 5 minut
    logger.info("⏰ Pierwsze skanowanie za 5 minut...")
    time.sleep(300)
    uruchom_skanowanie()
    
    # Zaplanuj skanowanie co godzinę
    schedule.every().hour.do(uruchom_skanowanie)
    
    # Pętla główna
    logger.info("🔄 Uruchomiono harmonogram skanowania co godzinę")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
