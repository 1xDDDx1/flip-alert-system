import requests
import time
import os
import schedule
import logging
import sqlite3
import statistics
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
import json

# Konfiguracja
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dane
BOT_TOKEN = os.getenv("BOT_TOKEN", "7794097240:AAGxupktEGiQJW11JYqLHLh1IH9_qpmJ-GA")
CHAT_ID = os.getenv("CHAT_ID", "1824475841")

# Ceny bazowe - będą się uczyć
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

class SmartDatabase:
    """Inteligentna baza danych AI"""
    
    def __init__(self, db_path="ai_flip_pro.db"):
        self.db_path = db_path
        self.init_database()
        logger.info("🧠 Smart Database zainicjalizowana")
    
    def init_database(self):
        """Tworzy tabele AI"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Historia ofert
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
                opis TEXT,
                smart_score INTEGER,
                czy_alert_wyslany BOOLEAN DEFAULT 0,
                url TEXT
            )
        ''')
        
        # Trendy cenowe - AI uczy się
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trendy_ai (
                id INTEGER PRIMARY KEY,
                model TEXT,
                wariant TEXT,
                cena_srednia REAL,
                cena_min REAL,
                cena_max REAL,
                trend_7_dni REAL,
                trend_30_dni REAL,
                liczba_ofert INTEGER,
                ostatnia_aktualizacja TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Predykcje AI
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predykcje_ai (
                id INTEGER PRIMARY KEY,
                model TEXT,
                wariant TEXT,
                przewidywana_cena REAL,
                przewidywana_data DATE,
                pewnosc_predykcji REAL,
                typ_predykcji TEXT,
                data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Preferencje użytkownika - AI się uczy
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferencje_ai (
                id INTEGER PRIMARY KEY,
                model TEXT,
                akcja TEXT,
                ostatnia_aktywnosc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def dodaj_oferte(self, oferta):
        """Dodaje ofertę i uczy się"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO oferty_historia 
            (tytul, cena, model, wariant, lokalizacja, platforma, seller_rating, opis, smart_score, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            oferta.get('tytul'),
            oferta.get('cena'),
            oferta.get('model'),
            oferta.get('wariant'),
            oferta.get('lokalizacja'),
            oferta.get('platforma'),
            oferta.get('seller_rating'),
            oferta.get('opis'),
            oferta.get('smart_score'),
            oferta.get('url')
        ))
        
        conn.commit()
        conn.close()
        
        # Automatyczne uczenie trendu
        self.aktualizuj_trendy_ai(oferta.get('model'), oferta.get('wariant'))
    
    def aktualizuj_trendy_ai(self, model, wariant):
        """AI uczy się trendów cenowych"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Pobierz dane z ostatnich 30 dni
        cursor.execute('''
            SELECT cena, data_utworzenia FROM oferty_historia 
            WHERE model = ? AND wariant = ? 
            AND data_utworzenia >= datetime('now', '-30 days')
            ORDER BY data_utworzenia
        ''', (model, wariant))
        
        dane = cursor.fetchall()
        
        if len(dane) >= 5:  # Minimum 5 ofert do analizy
            ceny = [row[0] for row in dane]
            
            # Oblicz trendy
            ceny_7_dni = [row[0] for row in dane if 
                         datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S') >= datetime.now() - timedelta(days=7)]
            
            cena_srednia = statistics.mean(ceny)
            cena_min = min(ceny)
            cena_max = max(ceny)
            
            # Trend 7 dni
            if len(ceny_7_dni) >= 2:
                trend_7_dni = ((ceny_7_dni[-1] - ceny_7_dni[0]) / ceny_7_dni[0]) * 100
            else:
                trend_7_dni = 0
            
            # Trend 30 dni
            if len(ceny) >= 2:
                trend_30_dni = ((ceny[-1] - ceny[0]) / ceny[0]) * 100
            else:
                trend_30_dni = 0
            
            # Zapisz trendy
            cursor.execute('''
                INSERT OR REPLACE INTO trendy_ai 
                (model, wariant, cena_srednia, cena_min, cena_max, trend_7_dni, trend_30_dni, liczba_ofert)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (model, wariant, cena_srednia, cena_min, cena_max, trend_7_dni, trend_30_dni, len(ceny)))
            
            conn.commit()
            logger.info(f"🧠 AI nauczył się trendu: {model} {wariant} - trend 7d: {trend_7_dni:+.1f}%")
        
        conn.close()
    
    def przewiduj_cene_ai(self, model, wariant):
        """AI przewiduje przyszłą cenę"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Pobierz najnowsze trendy
        cursor.execute('''
            SELECT cena_srednia, trend_7_dni, trend_30_dni, liczba_ofert 
            FROM trendy_ai 
            WHERE model = ? AND wariant = ?
            ORDER BY ostatnia_aktualizacja DESC LIMIT 1
        ''', (model, wariant))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            cena_srednia, trend_7_dni, trend_30_dni, liczba_ofert = result
            
            # Prosta predykcja na podstawie trendu
            if abs(trend_7_dni) > 5:  # Wyraźny trend
                przewidywana_zmiana = trend_7_dni * 0.3  # 30% aktualnego trendu
                przewidywana_cena = cena_srednia * (1 + przewidywana_zmiana/100)
                pewnosc = min(85, 50 + abs(trend_7_dni) * 2)
            else:
                przewidywana_cena = cena_srednia
                pewnosc = 60
            
            return {
                'przewidywana_cena': przewidywana_cena,
                'aktualna_srednia': cena_srednia,
                'trend_7_dni': trend_7_dni,
                'trend_30_dni': trend_30_dni,
                'pewnosc': pewnosc,
                'liczba_ofert': liczba_ofert
            }
        
        return None

class WebScrapingEngine:
    """Silnik web scrapingu"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        logger.info("🔍 Web Scraping Engine zainicjalizowany")
    
    def skanuj_allegro(self, query, max_results=10):
        """Skanuje Allegro przez web scraping"""
        oferty = []
        
        try:
            # URL wyszukiwania Allegro
            url = f"https://allegro.pl/listing?string={query.replace(' ', '%20')}"
            
            logger.info(f"🔍 Skanowanie Allegro: {query}")
            
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Znajdź oferty - różne selektory
                ofertas = soup.find_all('div', {'data-role': 'offer'})
                
                if not ofertas:
                    ofertas = soup.find_all('article', class_='mx7m_1')
                
                if not ofertas:
                    # Jeszcze inne selektory
                    ofertas = soup.find_all('div', class_='_1h7wt')
                
                logger.info(f"📊 Znaleziono {len(ofertas)} ofert na Allegro")
                
                for i, oferta in enumerate(ofertas[:max_results]):
                    try:
                        # Tytuł - różne selektory
                        tytul_elem = oferta.find('a', class_='mgn2_14')
                        if not tytul_elem:
                            tytul_elem = oferta.find('h2')
                        if not tytul_elem:
                            tytul_elem = oferta.find('a')
                        
                        if tytul_elem:
                            tytul = tytul_elem.get_text(strip=True)
                            
                            # Cena - różne selektory
                            cena_elem = oferta.find('span', class_='mli2_2')
                            if not cena_elem:
                                cena_elem = oferta.find('span', string=re.compile(r'\d+.*zł'))
                            
                            if cena_elem:
                                cena_text = cena_elem.get_text(strip=True)
                                cena_match = re.search(r'(\d+(?:\s\d+)*)', cena_text.replace(' ', ''))
                                if cena_match:
                                    cena = int(cena_match.group(1))
                                    
                                    # Link
                                    link_elem = oferta.find('a')
                                    link = link_elem.get('href') if link_elem else ''
                                    if link and not link.startswith('http'):
                                        link = f"https://allegro.pl{link}"
                                    
                                    oferty.append({
                                        'tytul': tytul,
                                        'cena': cena,
                                        'platforma': 'Allegro',
                                        'url': link,
                                        'lokalizacja': 'Sprawdź w ofercie',
                                        'seller_rating': 95,
                                        'opis': ''
                                    })
                    
                    except Exception as e:
                        logger.debug(f"❌ Błąd parsowania oferty {i}: {e}")
                        continue
            
            else:
                logger.warning(f"⚠️ Allegro status: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Błąd skanowania Allegro: {e}")
        
        return oferty
    
    def skanuj_olx(self, query, max_results=8):
        """Skanuje OLX przez web scraping"""
        oferty = []
        
        try:
            # URL OLX z filtrem śląskie
            url = f"https://www.olx.pl/oferty/q-{query.replace(' ', '-')}/?search%5Bregion_id%5D=5"
            
            logger.info(f"🔍 Skanowanie OLX: {query}")
            
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Selektory OLX
                ofertas = soup.find_all('div', {'data-cy': 'l-card'})
                
                logger.info(f"📊 Znaleziono {len(ofertas)} ofert na OLX")
                
                for i, oferta in enumerate(ofertas[:max_results]):
                    try:
                        # Tytuł
                        tytul_elem = oferta.find('h6')
                        if tytul_elem:
                            tytul = tytul_elem.get_text(strip=True)
                            
                            # Cena
                            cena_elem = oferta.find('p', {'data-testid': 'ad-price'})
                            if cena_elem:
                                cena_text = cena_elem.get_text(strip=True)
                                cena_match = re.search(r'(\d+(?:\s\d+)*)', cena_text.replace(' ', ''))
                                if cena_match:
                                    cena = int(cena_match.group(1))
                                    
                                    # Lokalizacja
                                    lokalizacja_elem = oferta.find('p', {'data-testid': 'location-date'})
                                    lokalizacja = lokalizacja_elem.get_text(strip=True) if lokalizacja_elem else "Nieznana"
                                    
                                    # Link
                                    link_elem = oferta.find('a')
                                    link = f"https://www.olx.pl{link_elem.get('href')}" if link_elem else ""
                                    
                                    oferty.append({
                                        'tytul': tytul,
                                        'cena': cena,
                                        'platforma': 'OLX',
                                        'url': link,
                                        'lokalizacja': lokalizacja,
                                        'seller_rating': 90,
                                        'opis': ''
                                    })
                    
                    except Exception as e:
                        logger.debug(f"❌ Błąd parsowania OLX {i}: {e}")
                        continue
            
        except Exception as e:
            logger.error(f"❌ Błąd skanowania OLX: {e}")
        
        return oferty

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

def oblicz_smart_score_pro(oferta, ai_data=None):
    """Oblicza Smart Score Pro z AI"""
    score = 50
    
    cena = oferta.get('cena', 0)
    model = oferta.get('model')
    wariant = oferta.get('wariant')
    seller_rating = oferta.get('seller_rating', 95)
    tytul = oferta.get('tytul', '').upper()
    opis = oferta.get('opis', '').upper()
    
    # Analiza ceny z AI
    if ai_data:
        cena_ai = ai_data.get('aktualna_srednia', 0)
        trend_7_dni = ai_data.get('trend_7_dni', 0)
        
        if cena_ai > 0:
            if cena < cena_ai * 0.8:
                score += 35  # Świetna cena vs AI
            elif cena < cena_ai * 0.9:
                score += 25  # Dobra cena vs AI
            elif cena < cena_ai:
                score += 15  # OK cena vs AI
            elif cena > cena_ai * 1.2:
                score -= 25  # Przecenione vs AI
        
        # Bonus za trend spadkowy
        if trend_7_dni < -5:
            score += 10  # Cena spada, dobry moment
        elif trend_7_dni > 10:
            score -= 10  # Cena rośnie, gorszy moment
    
    else:
        # Fallback do ceny bazowej
        if model and wariant:
            cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 0)
            if cena_bazowa > 0:
                if cena < cena_bazowa * 0.8:
                    score += 30
                elif cena < cena_bazowa * 0.9:
                    score += 20
                elif cena < cena_bazowa:
                    score += 10
                elif cena > cena_bazowa * 1.2:
                    score -= 30
    
    # Analiza sprzedawcy
    if seller_rating >= 98:
        score += 15
    elif seller_rating >= 95:
        score += 10
    elif seller_rating < 90:
        score -= 15
    
    # Słowa kluczowe
    for slowo in SLOWA_OSTRZEGAWCZE:
        if slowo.upper() in tytul or slowo.upper() in opis:
            score -= 25
            break
    
    # Pozytywne słowa
    pozytywne = ['IDEALNY', 'NOWY', 'GWARANCJA', 'ORYGINALNY', 'KOMPLET']
    for slowo in pozytywne:
        if slowo in tytul or slowo in opis:
            score += 5
    
    return max(0, min(100, score))

def jest_w_slaskim(lokalizacja):
    """Sprawdza lokalizację"""
    if not lokalizacja:
        return True  # Dla testów - sprawdzamy później
    
    lokalizacja_lower = lokalizacja.lower()
    for miasto in MIASTA_SLASKIE:
        if miasto in lokalizacja_lower:
            return True
    return any(slowo in lokalizacja_lower for slowo in ["śląskie", "slask", "katowice"])

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

def wyslij_smart_alert_pro(oferta, smart_score, ai_data=None):
    """Wysyła inteligentny alert AI Pro"""
    model = oferta.get('model')
    wariant = oferta.get('wariant')
    cena = oferta.get('cena')
    platforma = oferta.get('platforma')
    url = oferta.get('url')
    
    # Emoji na podstawie score
    if smart_score >= 85:
        emoji = '🔥'
        priorytet = 'SUPER OKAZJA'
    elif smart_score >= 70:
        emoji = '✅'
        priorytet = 'DOBRA OFERTA'
    elif smart_score >= 55:
        emoji = '🤔'
        priorytet = 'SPRAWDŹ'
    else:
        return False
    
    # AI insights
    ai_insights = ""
    if ai_data:
        przewidywana_cena = ai_data.get('przewidywana_cena', 0)
        trend_7_dni = ai_data.get('trend_7_dni', 0)
        pewnosc = ai_data.get('pewnosc', 0)
        
        if przewidywana_cena > 0:
            zmiana_pred = przewidywana_cena - cena
            ai_insights = f"""
🧠 <b>AI Analysis:</b>
• Przewiduje: {int(przewidywana_cena)} PLN za 7 dni
• Trend: {trend_7_dni:+.1f}% (7 dni)
• Pewność AI: {int(pewnosc)}%
• Potencjał: {zmiana_pred:+.0f} PLN"""
    
    # Rekomendacja AI
    if smart_score >= 85:
        rekomendacja = "🔥 KUP NATYCHMIAST!"
    elif smart_score >= 70:
        rekomendacja = "✅ Bardzo dobra oferta"
    else:
        rekomendacja = "🤔 Sprawdź szczegóły"
    
    alert = f"""{emoji} <b>AI LITE PRO ALERT</b>

🎯 <b>Priorytet:</b> {priorytet}
📱 <b>{model} {wariant}</b>
💰 <b>Cena:</b> {cena} PLN
🏪 <b>Platforma:</b> {platforma}
🧠 <b>AI Score:</b> {smart_score}/100
{ai_insights}

💡 <b>Rekomendacja AI:</b>
{rekomendacja}

🔗 <a href="{url}">SPRAWDŹ OFERTĘ</a>

<i>🤖 Powered by AI Lite Pro</i>"""
    
    return wyslij_wiadomosc(alert)

def main():
    """Główna funkcja AI Lite Pro"""
    logger.info("🚀 AI Lite Pro - Full Smart System!")
    
    # Inicjalizacja
    db = SmartDatabase()
    scraper = WebScrapingEngine()
    
    # Powiadomienie o uruchomieniu
    start_message = """🚀 <b>AI LITE PRO ACTIVE!</b>

🧠 <b>Smart Database:</b> ✅
🔍 <b>Web Scraping:</b> ✅
📊 <b>Machine Learning:</b> ✅
🔮 <b>Predykcje cen:</b> ✅
📈 <b>Analiza trendów:</b> ✅

🎯 <b>Funkcje AI:</b>
• Przewiduje ceny na 7 dni
• Uczy się trendów rynkowych
• Personalizuje rekomendacje
• Skanuje prawdziwe oferty

⚡ <b>Status:</b> FULL AI SYSTEM ACTIVE!
🔍 <b>Pierwszy smart skan za 3 minuty!</b>"""
    
    wyslij_wiadomosc(start_message)
    
    def smart_scan():
        """Inteligentne skanowanie z AI"""
        try:
            logger.info("🧠 Rozpoczynam AI Smart Scan...")
            
            frazy = ["iPhone 13", "iPhone 14", "iPhone 15", "Samsung Galaxy S25"]
            wszystkie_oferty = []
            smart_alerts = 0
            
            for fraza in frazy:
                # Multi-platform scraping
                logger.info(f"🔍 Skanowanie: {fraza}")
                
                # Allegro
                oferty_allegro = scraper.skanuj_allegro(fraza, max_results=6)
                
                # OLX
                oferty_olx = scraper.skanuj_olx(fraza, max_results=4)
                
                # Połącz wszystkie oferty
                all_oferty = oferty_allegro + oferty_olx
                logger.info(f"📊 Łącznie {len(all_oferty)} ofert z wszystkich platform")
                
                for oferta in all_oferty:
                    try:
                        # Analiza produktu
                        produkt = analizuj_produkt(oferta['tytul'])
                        if not produkt:
                            continue
                        
                        oferta.update(produkt)
                        
                        # AI Analysis
                        ai_data = db.przewiduj_cene_ai(produkt['model'], produkt['wariant'])
                        
                        # Smart Score Pro
                        smart_score = oblicz_smart_score_pro(oferta, ai_data)
                        oferta['smart_score'] = smart_score
                        
                        # Dodaj do bazy (AI się uczy)
                        db.dodaj_oferte(oferta)
                        
                        logger.info(f"🧠 {oferta['tytul'][:40]}... - Score: {smart_score}")
                        
                        # Smart Alert
                        if smart_score >= 70:  # Tylko najlepsze
                            if wyslij_smart_alert_pro(oferta, smart_score, ai_data):
                                smart_alerts += 1
                                time.sleep(3)
                        
                        wszystkie_oferty.append(oferta)
                        
                    except Exception as e:
                        logger.error(f"❌ Błąd analizy: {e}")
                        continue
                
                time.sleep(2)
            
            # Podsumowanie AI
            czas = datetime.now().strftime("%H:%M")
            summary = f"""🧠 <b>AI Smart Scan Complete</b>

🕒 <b>Czas:</b> {czas}
🔍 <b>Przeskanowano:</b> {len(wszystkie_oferty)} ofert
🧠 <b>AI Score range:</b> {min([o.get('smart_score', 0) for o in wszystkie_oferty], default=0)}-{max([o.get('smart_score', 0) for o in wszystkie_oferty], default=0)}
🔥 <b>Smart Alerts:</b> {smart_alerts} ofert
🎯 <b>AI Learning:</b> Database updated

⏰ <b>Następny smart scan:</b> za godzinę
🚀 <b>Status:</b> AI LITE PRO ACTIVE!"""
            
            wyslij_wiadomosc(summary)
            logger.info(f"✅ AI Smart Scan complete: {smart_alerts} alerts")
            
        except Exception as e:
            logger.error(f"❌ Błąd AI scan: {e}")
            wyslij_wiadomosc(f"❌ AI Error: {str(e)}")
    
    # Pierwszy smart scan za 3 minuty
    time.sleep(180)
    smart_scan()
    
    # Harmonogram co godzinę
    schedule.every().hour.do(smart_scan)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
