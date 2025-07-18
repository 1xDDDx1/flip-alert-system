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
    "bytom", "rybnik", "ruda śląska", "tychy", "dąbrowa górnicza", "chorzów"
]

class SmartDatabaseLite:
    """Lekka baza danych AI bez ciężkich zależności"""
    
    def __init__(self, db_path="smart_flip_lite.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicjalizuje bazę danych"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oferty_historia (
                id INTEGER PRIMARY KEY,
                data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tytul TEXT,
                cena REAL,
                model TEXT,
                wariant TEXT,
                lokalizacja TEXT,
                platforma TEXT,
                seller_rating REAL,
                czy_wysłano_alert BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ceny_dynamiczne (
                id INTEGER PRIMARY KEY,
                model TEXT,
                wariant TEXT,
                cena_srednia REAL,
                cena_min REAL,
                cena_max REAL,
                liczba_ofert INTEGER,
                ostatnia_aktualizacja TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Lekka baza danych AI zainicjalizowana")
    
    def dodaj_oferte(self, oferta):
        """Dodaje ofertę do historii"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO oferty_historia 
            (tytul, cena, model, wariant, lokalizacja, platforma, seller_rating)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            oferta.get('tytul'),
            oferta.get('cena'),
            oferta.get('model'),
            oferta.get('wariant'),
            oferta.get('lokalizacja'),
            oferta.get('platforma'),
            oferta.get('seller_rating')
        ))
        
        conn.commit()
        conn.close()
    
    def aktualizuj_ceny_dynamiczne(self, model, wariant):
        """Aktualizuje dynamiczne ceny na podstawie historii"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Pobierz ceny z ostatnich 30 dni
        cursor.execute('''
            SELECT cena FROM oferty_historia 
            WHERE model = ? AND wariant = ? 
            AND data_utworzenia >= datetime('now', '-30 days')
            AND cena > 0
        ''', (model, wariant))
        
        ceny = [row[0] for row in cursor.fetchall()]
        
        if len(ceny) >= 3:  # Minimum 3 oferty do analizy
            cena_srednia = statistics.mean(ceny)
            cena_min = min(ceny)
            cena_max = max(ceny)
            
            # Zapisz lub zaktualizuj
            cursor.execute('''
                INSERT OR REPLACE INTO ceny_dynamiczne 
                (model, wariant, cena_srednia, cena_min, cena_max, liczba_ofert, ostatnia_aktualizacja)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (model, wariant, cena_srednia, cena_min, cena_max, len(ceny)))
            
            conn.commit()
            logger.info(f"🧠 Zaktualizowano AI ceny dla {model} {wariant}: śr. {int(cena_srednia)} PLN")
        
        conn.close()
        return ceny
    
    def pobierz_cene_ai(self, model, wariant):
        """Pobiera inteligentną cenę referencyjną"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT cena_srednia, cena_min, cena_max, liczba_ofert 
            FROM ceny_dynamiczne 
            WHERE model = ? AND wariant = ?
            AND ostatnia_aktualizacja >= datetime('now', '-7 days')
        ''', (model, wariant))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'srednia': result[0],
                'min': result[1],
                'max': result[2],
                'liczba_ofert': result[3],
                'typ': 'ai_learned'
            }
        else:
            # Fallback do ceny bazowej
            bazowa = CENY_BAZOWE.get(model, {}).get(wariant)
            if bazowa:
                return {
                    'srednia': bazowa,
                    'min': bazowa * 0.8,
                    'max': bazowa * 1.2,
                    'liczba_ofert': 0,
                    'typ': 'baseline'
                }
        
        return None

class SmartAnalyzerLite:
    """Lekki analizator AI"""
    
    def __init__(self, database):
        self.db = database
    
    def analizuj_trend(self, model, wariant):
        """Analizuje trend cenowy bez ML"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Pobierz ceny z ostatnich 14 dni
        cursor.execute('''
            SELECT cena, data_utworzenia FROM oferty_historia 
            WHERE model = ? AND wariant = ? 
            AND data_utworzenia >= datetime('now', '-14 days')
            ORDER BY data_utworzenia
        ''', (model, wariant))
        
        dane = cursor.fetchall()
        conn.close()
        
        if len(dane) < 3:
            return {
                'trend': 'nieznany',
                'zmiana': 0,
                'rekomendacja': '🤔 Za mało danych',
                'pewnosc': 30
            }
        
        # Proste obliczenie trendu
        ceny_stare = [row[0] for row in dane[:len(dane)//2]]
        ceny_nowe = [row[0] for row in dane[len(dane)//2:]]
        
        srednia_stara = statistics.mean(ceny_stare)
        srednia_nowa = statistics.mean(ceny_nowe)
        
        zmiana = ((srednia_nowa - srednia_stara) / srednia_stara) * 100
        
        if zmiana > 5:
            trend = 'rosnący'
            rekomendacja = '⏳ Cena rośnie - rozważ szybki zakup'
            pewnosc = min(85, 60 + abs(zmiana))
        elif zmiana < -5:
            trend = 'spadający'
            rekomendacja = '📉 Cena spada - poczekaj na lepszą ofertę'
            pewnosc = min(85, 60 + abs(zmiana))
        else:
            trend = 'stabilny'
            rekomendacja = '✅ Stabilna cena - dobry moment'
            pewnosc = 70
        
        return {
            'trend': trend,
            'zmiana': round(zmiana, 1),
            'rekomendacja': rekomendacja,
            'pewnosc': int(pewnosc)
        }
    
    def oblicz_smart_score(self, oferta, cena_ai):
        """Oblicza inteligentny wynik oferty"""
        score = 50  # Bazowy wynik
        
        cena = oferta.get('cena', 0)
        seller_rating = oferta.get('seller_rating', 95)
        tytul = oferta.get('tytul', '').upper()
        opis = oferta.get('opis', '').upper()
        
        # Analiza ceny
        if cena_ai:
            if cena < cena_ai['srednia'] * 0.8:
                score += 30  # Świetna cena
            elif cena < cena_ai['srednia'] * 0.9:
                score += 20  # Dobra cena
            elif cena < cena_ai['srednia']:
                score += 10  # OK cena
            elif cena > cena_ai['srednia'] * 1.2:
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
    """Klasa API Allegro (bez zmian)"""
    
    def __init__(self):
        self.client_id = ALLEGRO_CLIENT_ID
        self.client_secret = ALLEGRO_CLIENT_SECRET
        self.access_token = None
        self.base_url = "https://api.allegro.pl"
    
    def get_access_token(self):
        """Pobiera access token"""
        try:
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            
            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {"grant_type": "client_credentials"}
            
            response = requests.post(f"{self.base_url}/auth/oauth/token", headers=headers, data=data)
            
            if response.status_code == 200:
                self.access_token = response.json()["access_token"]
                logger.info("✅ Token Allegro otrzymany")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Błąd tokena: {e}")
            return False
    
    def search_products(self, query, limit=15):
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
            return []
        except Exception as e:
            logger.error(f"❌ Błąd wyszukiwania: {e}")
            return []

def analizuj_produkt(tytul, opis=""):
    """Analizuje produkt (bez zmian)"""
    tekst = (tytul + " " + opis).upper()
    
    for model in CENY_BAZOWE:
        if model.upper() in tekst:
            for wariant in CENY_BAZOWE[model]:
                if wariant.upper() in tekst:
                    return {"model": model, "wariant": wariant}
            return {"model": model, "wariant": list(CENY_BAZOWE[model].keys())[0]}
    return None

def jest_w_slaskim(lokalizacja):
    """Sprawdza lokalizację (bez zmian)"""
    if not lokalizacja:
        return False
    
    lokalizacja_lower = lokalizacja.lower()
    for miasto in MIASTA_SLASKIE:
        if miasto in lokalizacja_lower:
            return True
    return any(slowo in lokalizacja_lower for slowo in ["śląskie", "slask", "katowice"])

def wyslij_smart_alert(oferta, cena_ai, smart_score, trend_analiza):
    """Wysyła inteligentny alert AI Lite"""
    model = oferta.get('model')
    wariant = oferta.get('wariant')
    cena = oferta.get('cena')
    lokalizacja = oferta.get('lokalizacja')
    link = oferta.get('link')
    
    # Określ priorytet na podstawie smart_score
    if smart_score >= 80:
        emoji = '🔥'
        priorytet = 'SUPER OKAZJA'
        kolor = 'czerwony'
    elif smart_score >= 65:
        emoji = '✅'
        priorytet = 'DOBRA OFERTA'
        kolor = 'zielony'
    elif smart_score >= 50:
        emoji = '🤔'
        priorytet = 'SPRAWDŹ'
        kolor = 'żółty'
    else:
        return False  # Nie wysyłaj słabych ofert
    
    # Oblicz oszczędności
    if cena_ai:
        oszczednosci = int(cena_ai['srednia'] - cena)
        procent_oszczednosci = ((cena_ai['srednia'] - cena) / cena_ai['srednia']) * 100
    else:
        oszczednosci = 0
        procent_oszczednosci = 0
    
    alert = f"""{emoji} <b>SMART ALERT AI LITE</b>

🧠 <b>AI Score:</b> {smart_score}/100 ({priorytet})
📱 <b>{model} {wariant}</b>
💰 <b>Cena:</b> {cena} PLN

📊 <b>Analiza AI:</b>
• Średnia rynkowa: {int(cena_ai['srednia']) if cena_ai else 'N/A'} PLN
• Typ ceny: {cena_ai['typ'] if cena_ai else 'bazowa'}
• Ofert w bazie: {cena_ai['liczba_ofert'] if cena_ai else 0}

📈 <b>Trend ({trend_analiza['pewnosc']}% pewności):</b>
• {trend_analiza['trend'].upper()} ({trend_analiza['zmiana']:+.1f}%)
• {trend_analiza['rekomendacja']}

💡 <b>Rekomendacja AI:</b>
{"🔥 KUP NATYCHMIAST!" if smart_score >= 80 else "✅ Warto rozważyć" if smart_score >= 65 else "🤔 Sprawdź szczegóły"}

💰 <b>Potencjalne zyski:</b> {oszczednosci:+d} PLN ({procent_oszczednosci:+.1f}%)
📍 <b>Lokalizacja:</b> {lokalizacja}

🔗 <a href="{link}">SPRAWDŹ PRAWDZIWĄ OFERTĘ</a>

<i>🤖 Powered by AI Lite</i>"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dane = {
        "chat_id": CHAT_ID,
        "text": alert,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=dane)
        if response.status_code == 200:
            logger.info(f"🤖 Smart alert wysłany (Score: {smart_score})")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Błąd alertu: {e}")
        return False

def main():
    """Główna funkcja AI Lite"""
    logger.info("🤖 Smart Flip Alert AI LITE uruchomiony!")
    
    # Inicjalizacja
    db = SmartDatabaseLite()
    analyzer = SmartAnalyzerLite(db)
    allegro = AllegroAPI()
    
    # Powiadomienie o uruchomieniu
    start_message = """🤖 <b>SMART FLIP ALERT - AI LITE!</b>

🧠 <b>Lekka Sztuczna Inteligencja:</b>
✅ Dynamiczne uczenie się cen
✅ Inteligentny scoring ofert (0-100)
✅ Analiza trendów bez ML
✅ Smart rekomendacje
✅ Baza historii wszystkich ofert

📊 <b>AI Lite Features:</b>
• Smart Score: 80+ = 🔥 SUPER OKAZJA
• Smart Score: 65+ = ✅ DOBRA OFERTA  
• Smart Score: 50+ = 🤔 SPRAWDŹ
• Dynamiczne ceny referencyjne
• Analiza trendów bez ciężkich bibliotek

⚡ <b>Status:</b> AI LITE AKTYWNE!
💾 <b>Hosting:</b> Lekkie, stabilne, szybkie

<i>🚀 Inteligentny flipping bez problemów!</i>"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dane = {"chat_id": CHAT_ID, "text": start_message, "parse_mode": "HTML"}
    requests.post(url, json=dane)
    
    def skanuj_i_analizuj():
        """Skanowanie z AI Lite"""
        try:
            logger.info("🔍 Rozpoczynam inteligentne skanowanie...")
            
            frazy = ["iPhone 13", "iPhone 14", "iPhone 15", "Samsung Galaxy S25", "PlayStation 5"]
            wszystkie_oferty = []
            
            for fraza in frazy:
                oferty = allegro.search_products(fraza, limit=8)
                
                for oferta in oferty:
                    try:
                        tytul = oferta.get("name", "")
                        cena = int(float(oferta.get("price", {}).get("amount", 0)))
                        lokalizacja = oferta.get("vendor", {}).get("location", {}).get("city", "")
                        link = f"https://allegro.pl/oferta/{oferta.get('id', '')}"
                        seller_rating = oferta.get("vendor", {}).get("rating", {}).get("percentage", 95)
                        
                        if not jest_w_slaskim(lokalizacja) or cena == 0:
                            continue
                        
                        # Analiza produktu
                        produkt = analizuj_produkt(tytul)
                        if not produkt:
                            continue
                        
                        oferta_data = {
                            'tytul': tytul,
                            'cena': cena,
                            'model': produkt['model'],
                            'wariant': produkt['wariant'],
                            'lokalizacja': lokalizacja,
                            'platforma': 'Allegro',
                            'seller_rating': seller_rating,
                            'link': link,
                            'opis': ''
                        }
                        
                        wszystkie_oferty.append(oferta_data)
                        
                    except Exception as e:
                        logger.error(f"❌ Błąd oferty: {e}")
                        continue
                
                time.sleep(1)
            
            # Analizuj każdą ofertę AI
            dobre_oferty = 0
            for oferta in wszystkie_oferty:
                try:
                    # Dodaj do historii
                    db.dodaj_oferte(oferta)
                    
                    # Aktualizuj ceny AI
                    db.aktualizuj_ceny_dynamiczne(oferta['model'], oferta['wariant'])
                    
                    # Pobierz inteligentną cenę
                    cena_ai = db.pobierz_cene_ai(oferta['model'], oferta['wariant'])
                    
                    # Analiza trendu
                    trend = analyzer.analizuj_trend(oferta['model'], oferta['wariant'])
                    
                    # Smart score
                    smart_score = analyzer.oblicz_smart_score(oferta, cena_ai)
                    
                    logger.info(f"📱 {oferta['tytul'][:50]}... - Score: {smart_score}")
                    
                    # Wyślij alert jeśli wystarczająco dobry
                    if smart_score >= 65:  # Próg dla alertów
                        if wyslij_smart_alert(oferta, cena_ai, smart_score, trend):
                            dobre_oferty += 1
                            time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"❌ Błąd analizy AI: {e}")
                    continue
            
            # Podsumowanie
            czas = datetime.now().strftime("%H:%M")
            summary = f"""📊 <b>AI Lite - Podsumowanie</b>

🕒 <b>Czas:</b> {czas}
🤖 <b>Przeanalizowano:</b> {len(wszystkie_oferty)} ofert
✅ <b>Smart alerty:</b> {dobre_oferty} ofert
🧠 <b>AI:</b> Ceny zaktualizowane, trendy przeanalizowane

⏰ <b>Następne skanowanie:</b> za godzinę
🎯 <b>Status:</b> AI Lite w pełnej gotowości!

<i>🚀 Smart flipping działa!</i>"""
            
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            dane = {"chat_id": CHAT_ID, "text": summary, "parse_mode": "HTML"}
            requests.post(url, json=dane)
            
            logger.info(f"✅ Skanowanie zakończone: {dobre_oferty} alertów")
            
        except Exception as e:
            logger.error(f"❌ Błąd skanowania: {e}")
    
    # Pierwsze skanowanie za 5 minut
    time.sleep(300)
    skanuj_i_analizuj()
    
    # Harmonogram
    schedule.every().hour.do(skanuj_i_analizuj)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
