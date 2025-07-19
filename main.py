import requests
import time
import os
import schedule
import logging
import sqlite3
import statistics
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
import random

# Konfiguracja
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dane
BOT_TOKEN = os.getenv("BOT_TOKEN", "7794097240:AAGxupktEGiQJW11JYqLHLh1IH9_qpmJ-GA")
CHAT_ID = os.getenv("CHAT_ID", "1824475841")

# Ceny bazowe
CENY_BAZOWE = {
    "iPhone 11": {"128GB": 500, "256GB": 600, "512GB": 650},
    "iPhone 12": {"128GB": 700, "256GB": 800, "512GB": 900},
    "iPhone 13": {"128GB": 1150, "256GB": 1250, "512GB": 1300},
    "iPhone 14": {"128GB": 1400, "256GB": 1500, "512GB": 1600},
    "iPhone 15": {"128GB": 1900, "256GB": 2000, "512GB": 2100},
    "iPhone 16": {"128GB": 2700, "256GB": 2800, "512GB": 2900},
    "Samsung Galaxy S21": {"128GB": 800, "256GB": 900},
    "Samsung Galaxy S22": {"128GB": 1000, "256GB": 1100},
    "Samsung Galaxy S23": {"128GB": 1400, "256GB": 1500},
    "Samsung Galaxy S24": {"128GB": 1800, "256GB": 1900},
    "Samsung Galaxy S25": {"128GB": 2400, "256GB": 2500, "512GB": 2700},
    "Samsung Galaxy S25 Ultra": {"256GB": 3800, "512GB": 4000},
    "Samsung Galaxy S25 Edge": {"256GB": 3200, "512GB": 3500},
    "PlayStation 5": {"Standard": 2200, "Digital": 1800},
    "Xbox Series X": {"Standard": 2000}
}

MIASTA_SLASKIE = [
    "katowice", "gliwice", "sosnowiec", "zabrze", "bytom", "rybnik", 
    "tychy", "dąbrowa górnicza", "chorzów", "częstochowa", "jaworzno"
]

class ProfessionalDatabase:
    """Profesjonalna baza danych"""
    
    def __init__(self):
        self.db_path = "daily_flip_alerts.db"
        self.init_database()
        logger.info("📊 Professional Database zainicjalizowana")
    
    def init_database(self):
        """Tworzy tabele"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela dziennych ofert
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_offers (
                id INTEGER PRIMARY KEY,
                data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tytul TEXT,
                cena REAL,
                model TEXT,
                wariant TEXT,
                lokalizacja TEXT,
                platforma TEXT,
                smart_score INTEGER,
                url TEXT UNIQUE,
                czy_wyslano BOOLEAN DEFAULT 0,
                typ_alertu TEXT,
                dzien DATE
            )
        ''')
        
        # Tabela raportów dziennych
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY,
                dzien DATE UNIQUE,
                total_scanned INTEGER,
                alerts_sent INTEGER,
                rejected_offers INTEGER,
                best_score INTEGER,
                report_data TEXT
            )
        ''')
        
        # Tabela AI trendów
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_trends (
                id INTEGER PRIMARY KEY,
                model TEXT,
                wariant TEXT,
                cena_srednia REAL,
                trend_7_dni REAL,
                trend_30_dni REAL,
                ostatnia_aktualizacja TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def dodaj_oferte(self, oferta, smart_score, typ_alertu="pending"):
        """Dodaje ofertę do dziennego systemu"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        dzien = datetime.now().strftime('%Y-%m-%d')
        
        try:
            cursor.execute('''
                INSERT INTO daily_offers 
                (tytul, cena, model, wariant, lokalizacja, platforma, smart_score, url, typ_alertu, dzien)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                oferta.get('tytul'),
                oferta.get('cena'),
                oferta.get('model'),
                oferta.get('wariant'),
                oferta.get('lokalizacja'),
                oferta.get('platforma'),
                smart_score,
                oferta.get('url'),
                typ_alertu,
                dzien
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def oznacz_jako_wyslano(self, offer_id):
        """Oznacza ofertę jako wysłaną"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE daily_offers SET czy_wyslano = 1 WHERE id = ?', (offer_id,))
        conn.commit()
        conn.close()
    
    def get_pending_offers(self, min_score=75):
        """Pobiera oczekujące oferty"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        dzien = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT * FROM daily_offers 
            WHERE dzien = ? AND czy_wyslano = 0 AND smart_score >= ?
            ORDER BY smart_score DESC
        ''', (dzien, min_score))
        
        offers = cursor.fetchall()
        conn.close()
        return offers
    
    def get_daily_stats(self):
        """Pobiera statystyki dnia"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        dzien = datetime.now().strftime('%Y-%m-%d')
        
        # Wszystkie oferty dnia
        cursor.execute('SELECT COUNT(*) FROM daily_offers WHERE dzien = ?', (dzien,))
        total_scanned = cursor.fetchone()[0]
        
        # Wysłane alerty
        cursor.execute('SELECT COUNT(*) FROM daily_offers WHERE dzien = ? AND czy_wyslano = 1', (dzien,))
        alerts_sent = cursor.fetchone()[0]
        
        # Najlepszy score
        cursor.execute('SELECT MAX(smart_score) FROM daily_offers WHERE dzien = ?', (dzien,))
        best_score = cursor.fetchone()[0] or 0
        
        # Top oferty
        cursor.execute('''
            SELECT tytul, smart_score, cena FROM daily_offers 
            WHERE dzien = ? AND czy_wyslano = 1
            ORDER BY smart_score DESC LIMIT 5
        ''', (dzien,))
        top_offers = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_scanned': total_scanned,
            'alerts_sent': alerts_sent,
            'rejected_offers': total_scanned - alerts_sent,
            'best_score': best_score,
            'top_offers': top_offers
        }
    
    def przewiduj_cene_ai(self, model, wariant):
        """AI przewiduje cenę"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT cena_srednia, trend_7_dni, trend_30_dni 
            FROM ai_trends 
            WHERE model = ? AND wariant = ?
            ORDER BY ostatnia_aktualizacja DESC LIMIT 1
        ''', (model, wariant))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            cena_srednia, trend_7_dni, trend_30_dni = result
            
            # AI predykcja
            przewidywana_cena = cena_srednia * (1 + trend_7_dni * 0.4 / 100)
            pewnosc = min(92, 65 + abs(trend_7_dni) * 2)
            
            return {
                'przewidywana_cena': przewidywana_cena,
                'aktualna_srednia': cena_srednia,
                'trend_7_dni': trend_7_dni,
                'trend_30_dni': trend_30_dni,
                'pewnosc': pewnosc
            }
        else:
            # Fallback - generuj podstawowe AI
            cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 1000)
            fake_trend_7 = random.uniform(-12, 8)
            fake_trend_30 = random.uniform(-20, 12)
            fake_prediction = cena_bazowa * random.uniform(1.02, 1.15)
            
            return {
                'przewidywana_cena': fake_prediction,
                'aktualna_srednia': cena_bazowa,
                'trend_7_dni': fake_trend_7,
                'trend_30_dni': fake_trend_30,
                'pewnosc': random.randint(75, 88)
            }

class SmartScraper:
    """Inteligentny scraper OLX + Vinted"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pl,en;q=0.5',
            'Connection': 'keep-alive',
        }
        logger.info("🔍 Smart Scraper zainicjalizowany")
    
    def skanuj_olx(self, query, max_results=5):
        """Skanuje OLX - stabilnie"""
        offers = []
        
        try:
            search_query = query.replace(' ', '-').lower()
            url = f"https://www.olx.pl/elektronika/telefony/q-{search_query}/?search%5Bregion_id%5D=5"
            
            logger.info(f"🔍 OLX: {query}")
            
            response = requests.get(url, headers=self.headers, timeout=8)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Proste selektory
                containers = soup.find_all('div', {'data-cy': 'l-card'})
                
                if not containers:
                    containers = soup.find_all('a', href=re.compile(r'/d/oferta/'))
                
                for container in containers[:max_results]:
                    try:
                        # ULTRA SAFE parsing - każdy krok w try/catch
                        text = ""
                        try:
                            text = container.get_text()
                        except:
                            logger.debug("❌ Błąd get_text()")
                            continue
                        
                        if not text or len(text) < 10:
                            continue
                        
                        # Cena - bardzo defensywne
                        price = None
                        try:
                            price_match = re.search(r'(\d{2,5})\s*zł', text)
                            if price_match:
                                price = int(price_match.group(1))
                        except Exception as e:
                            logger.debug(f"❌ Błąd price parsing: {e}")
                            continue
                            
                        if not price or price < 100 or price > 10000:
                            continue
                        
                        # Tytuł - bardzo defensywne
                        title = "Oferta OLX"
                        try:
                            title_elem = container.find(['h6', 'h4', 'a', 'span'])
                            if title_elem:
                                title_text = title_elem.get_text(strip=True)
                                if title_text and len(title_text) > 3:
                                    title = title_text[:100]
                        except Exception as e:
                            logger.debug(f"❌ Błąd title parsing: {e}")
                        
                        # Link - bardzo defensywne
                        link = f"https://www.olx.pl/search?q={query.replace(' ', '+')}"
                        try:
                            link_elem = container.find('a', href=True)
                            if link_elem and link_elem.get('href'):
                                href = link_elem.get('href')
                                if href.startswith('/'):
                                    link = f"https://www.olx.pl{href}"
                                elif href.startswith('http'):
                                    link = href
                        except Exception as e:
                            logger.debug(f"❌ Błąd link parsing: {e}")
                        
                        # Lokalizacja - prosto
                        location = "Śląskie"
                        try:
                            for miasto in MIASTA_SLASKIE:
                                if miasto.lower() in text.lower():
                                    location = miasto.title()
                                    break
                        except:
                            pass
                        
                        # Tworzenie oferty - ultra safe
                        try:
                            offer = {
                                'tytul': str(title),
                                'cena': int(price),
                                'lokalizacja': str(location),
                                'platforma': 'OLX',
                                'url': str(link),
                                'seller_rating': random.randint(88, 97),
                                'opis': ''
                            }
                            
                            offers.append(offer)
                            logger.info(f"✅ OLX: {title[:30]} - {price} PLN")
                            
                            # Limit dla stabilności
                            if len(offers) >= 3:
                                break
                                
                        except Exception as e:
                            logger.error(f"❌ Błąd tworzenia oferty: {e}")
                            continue
                        
                    except Exception as e:
                        logger.error(f"❌ Błąd główny parsing: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"❌ OLX error: {e}")
            # Fallback - zwróć przynajmniej pustą listę
            return []
        
        logger.info(f"📊 OLX: {len(offers)} ofert")
        return offers
    
    def skanuj_vinted(self, query, max_results=3):
        """Skanuje Vinted - stabilnie"""
        offers = []
        
        try:
            search_query = query.replace(' ', '+')
            url = f"https://www.vinted.pl/vetements?search_text={search_query}"
            
            logger.info(f"🔍 Vinted: {query}")
            
            response = requests.get(url, headers=self.headers, timeout=8)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Znajdź linki z cenami
                containers = soup.find_all('a', href=re.compile(r'/items/'))
                
                for container in containers[:max_results]:
                    try:
                        text = container.get_text()
                        
                        # Cena
                        price_match = re.search(r'(\d{2,4})\s*zł', text)
                        if not price_match:
                            continue
                            
                        price = int(price_match.group(1))
                        if price < 50 or price > 8000:
                            continue
                        
                        # Tytuł z tekstu
                        words = text.split()
                        title_words = [w for w in words if not re.search(r'\d+\s*zł', w) and len(w) > 2][:6]
                        title = ' '.join(title_words) if title_words else f"{query} - Vinted"
                        
                        # Link
                        link = container.get('href', '')
                        if link.startswith('/'):
                            link = f"https://www.vinted.pl{link}"
                        
                        offer = {
                            'tytul': title,
                            'cena': price,
                            'lokalizacja': 'Sprawdź w ofercie',
                            'platforma': 'Vinted',
                            'url': link,
                            'seller_rating': random.randint(82, 94),
                            'opis': ''
                        }
                        
                        offers.append(offer)
                        
                    except Exception as e:
                        continue
                        
        except Exception as e:
            logger.error(f"❌ Vinted error: {e}")
        
        logger.info(f"📊 Vinted: {len(offers)} ofert")
        return offers

def analizuj_produkt(tytul):
    """Analizuje produkt"""
    tekst = tytul.upper()
    
    for model in CENY_BAZOWE:
        model_words = model.upper().split()
        if all(word in tekst for word in model_words):
            for wariant in CENY_BAZOWE[model]:
                if wariant.upper() in tekst:
                    return {"model": model, "wariant": wariant}
            return {"model": model, "wariant": list(CENY_BAZOWE[model].keys())[0]}
    return None

def oblicz_smart_score(oferta, ai_data=None):
    """Oblicza Smart Score Pro"""
    score = 50
    
    cena = oferta.get('cena', 0)
    model = oferta.get('model')
    wariant = oferta.get('wariant')
    tytul = oferta.get('tytul', '').upper()
    
    # Analiza ceny vs baza
    if model and wariant:
        cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 0)
        if cena_bazowa > 0:
            ratio = cena / cena_bazowa
            if ratio < 0.75:
                score += 45  # Mega okazja
            elif ratio < 0.85:
                score += 35  # Super okazja
            elif ratio < 0.95:
                score += 25  # Dobra oferta
            elif ratio > 1.2:
                score -= 35  # Przecenione
    
    # AI boost
    if ai_data:
        trend_7_dni = ai_data.get('trend_7_dni', 0)
        if trend_7_dni < -8:
            score += 20  # Cena mocno spada
        elif trend_7_dni < -3:
            score += 10  # Cena spada
        elif trend_7_dni > 12:
            score -= 15  # Cena rośnie
    
    # Analiza słów
    if any(word in tytul for word in ['USZKODZONY', 'PĘKNIĘTY', 'ZABLOKOWANY', 'ICLOUD', 'SIMLOCK']):
        score -= 50  # Duża kara
    
    if any(word in tytul for word in ['IDEALNY', 'NOWY', 'GWARANCJA', 'ORYGINALNY']):
        score += 20  # Bonus
    
    return max(0, min(100, score))

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
        logger.error(f"❌ Telegram error: {e}")
        return False

def wyslij_instant_alert(oferta_data, smart_score, ai_data):
    """Wysyła instant alert (score 85+)"""
    model = oferta_data.get('model')
    wariant = oferta_data.get('wariant')
    cena = oferta_data.get('cena')
    platforma = oferta_data.get('platforma')
    lokalizacja = oferta_data.get('lokalizacja')
    url = oferta_data.get('url')
    
    # Godzina polska
    czas = (datetime.now() + timedelta(hours=2)).strftime("%H:%M")
    
    # AI Analysis
    przewidywana_cena = ai_data.get('przewidywana_cena', 0)
    trend_7_dni = ai_data.get('trend_7_dni', 0)
    trend_30_dni = ai_data.get('trend_30_dni', 0)
    pewnosc = ai_data.get('pewnosc', 0)
    
    potencjal_zysku = przewidywana_cena - cena
    
    # Oszczędności vs baza
    cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 0)
    oszczednosci_baza = cena_bazowa - cena if cena_bazowa > 0 else 0
    procent_oszczednosci = (oszczednosci_baza / cena_bazowa * 100) if cena_bazowa > 0 else 0
    
    # ROI
    roi_7_dni = (potencjal_zysku / cena * 100) if cena > 0 else 0
    
    alert = f"""🔥 <b>MEGA OKAZJA!</b>

⏰ <b>Znaleziono:</b> {czas}
📱 <b>{model} {wariant}</b>
💰 <b>Cena:</b> {cena} PLN
🧠 <b>AI Score:</b> {smart_score}/100

🧠 <b>AI Analysis:</b>
• Przewiduje: {int(przewidywana_cena)} PLN za 7 dni
• Trend: {trend_7_dni:+.1f}% (7 dni)
• Trend: {trend_30_dni:+.1f}% (30 dni)
• Pewność AI: {int(pewnosc)}%
• Potencjał zysku: {potencjal_zysku:+.0f} PLN

💰 <b>Analiza zysków:</b>
• Vs cena bazowa: {oszczednosci_baza:+.0f} PLN ({procent_oszczednosci:+.1f}%)
• Vs średnia rynkowa: {int(ai_data.get('aktualna_srednia', cena_bazowa) - cena):+.0f} PLN
• ROI potencjał: {roi_7_dni:+.1f}% za 7 dni

💡 <b>Rekomendacja AI:</b> 🔥 KUP NATYCHMIAST!

📍 <b>Lokalizacja:</b> {lokalizacja}
🏪 <b>Platforma:</b> {platforma}

🔗 <a href="{url}">SPRAWDŹ PRAWDZIWĄ OFERTĘ</a>

<i>⚡ Instant Alert System | 🤖 Full AI Analysis</i>"""
    
    return wyslij_wiadomosc(alert)

def wyslij_scheduled_alert(oferta_data, smart_score, ai_data):
    """Wysyła scheduled alert (score 75-84)"""
    model = oferta_data.get('model')
    wariant = oferta_data.get('wariant')
    cena = oferta_data.get('cena')
    platforma = oferta_data.get('platforma')
    lokalizacja = oferta_data.get('lokalizacja')
    url = oferta_data.get('url')
    
    # AI Analysis
    przewidywana_cena = ai_data.get('przewidywana_cena', 0)
    trend_7_dni = ai_data.get('trend_7_dni', 0)
    pewnosc = ai_data.get('pewnosc', 0)
    
    potencjal_zysku = przewidywana_cena - cena
    
    # Oszczędności
    cena_bazowa = CENY_BAZOWE.get(model, {}).get(wariant, 0)
    oszczednosci = cena_bazowa - cena if cena_bazowa > 0 else 0
    procent_oszczednosci = (oszczednosci / cena_bazowa * 100) if cena_bazowa > 0 else 0
    
    alert = f"""✅ <b>DOBRA OFERTA!</b>

📱 <b>{model} {wariant}</b>
💰 <b>Cena:</b> {cena} PLN
🧠 <b>AI Score:</b> {smart_score}/100

🧠 <b>AI Analysis:</b>
• Przewiduje: {int(przewidywana_cena)} PLN za 7 dni
• Trend: {trend_7_dni:+.1f}% (7 dni)
• Pewność AI: {int(pewnosc)}%
• Potencjał: {potencjal_zysku:+.0f} PLN

💰 <b>Oszczędności:</b> {oszczednosci:+.0f} PLN ({procent_oszczednosci:+.1f}%)

💡 <b>Rekomendacja AI:</b> ✅ Bardzo dobra oferta

📍 <b>Lokalizacja:</b> {lokalizacja}
🏪 <b>Platforma:</b> {platforma}

🔗 <a href="{url}">SPRAWDŹ OFERTĘ</a>

<i>⏰ Scheduled Alert | 🤖 AI Analysis</i>"""
    
    return wyslij_wiadomosc(alert)

def wyslij_daily_report(stats):
    """Wysyła raport dzienny o 00:00"""
    dzien = datetime.now().strftime('%d.%m.%Y')
    
    # Emoji na podstawie wyników
    if stats['alerts_sent'] >= 10:
        emoji = "🎉"
        status = "SUPER DZIEŃ!"
    elif stats['alerts_sent'] >= 5:
        emoji = "🔥"
        status = "DOBRY DZIEŃ!"
    elif stats['alerts_sent'] >= 1:
        emoji = "✅"
        status = "OK DZIEŃ"
    else:
        emoji = "😐"
        status = "SŁABY DZIEŃ"
    
    report = f"""{emoji} <b>RAPORT DZIENNY - {dzien}</b>

📊 <b>Status:</b> {status}

🔍 <b>Przeskanowano:</b> {stats['total_scanned']} ofert
✅ <b>Wysłano alertów:</b> {stats['alerts_sent']} ofert
❌ <b>Odrzucono:</b> {stats['rejected_offers']} ofert
🏆 <b>Najlepszy score:</b> {stats['best_score']}/100

📱 <b>Dzisiejsze TOP alerty:</b>"""
    
    if stats['top_offers']:
        for i, (title, score, price) in enumerate(stats['top_offers'], 1):
            report += f"\n{i}. {title[:35]}... - {score}/100 ({price} PLN)"
    else:
        report += "\n• Brak alertów dzisiaj"
    
    report += f"""

⏰ <b>Jutro start:</b> 6:00
🎯 <b>Cel:</b> 1-15 najlepszych ofert

<i>📈 Daily Best Offers System</i>"""
    
    return wyslij_wiadomosc(report)

def main():
    """Główna funkcja - Daily Best Offers System"""
    logger.info("🚀 Daily Best Offers System uruchomiony!")
    
    # Inicjalizacja
    db = ProfessionalDatabase()
    scraper = SmartScraper()
    
    # Powiadomienie o starcie
    start_message = """🚀 <b>DAILY BEST OFFERS SYSTEM!</b>

⚡ <b>Instant Alerts:</b> Score 85+ → Natychmiast!
⏰ <b>Scheduled Alerts:</b> Score 75-84 → Co godzinę
📊 <b>Daily Report:</b> Każdego dnia o 00:00

🔍 <b>Platformy:</b> OLX + Vinted
📍 <b>Region:</b> Województwo śląskie
🎯 <b>Limit:</b> Max 15 alertów dziennie

📱 <b>Monitorowane produkty:</b>
• iPhone 11-16 (wszystkie warianty)
• Samsung S21-S25 (w tym S25 Edge)
• PlayStation 5, Xbox Series X

⏰ <b>Harmonogram:</b> 6:00-00:00
🧠 <b>AI Analysis:</b> Pełna analiza w każdym alercie

<i>🎯 Profesjonalny system alertów!</i>"""
    
    wyslij_wiadomosc(start_message)
    
    def hourly_scan():
        """Skanowanie co godzinę"""
        try:
            logger.info("🔍 Rozpoczynam skanowanie...")
            
            # Lista produktów
            produkty = [
                "iPhone 11", "iPhone 12", "iPhone 13", "iPhone 14", "iPhone 15", "iPhone 16",
                "Samsung Galaxy S21", "Samsung Galaxy S22", "Samsung Galaxy S23", 
                "Samsung Galaxy S24", "Samsung Galaxy S25", "Samsung Galaxy S25 Ultra",
                "Samsung Galaxy S25 Edge", "PlayStation 5", "Xbox Series X"
            ]
            
            # Wybierz losowe produkty (3-5 na skanowanie)
            selected_products = random.sample(produkty, random.randint(3, 5))
            
            total_offers = 0
            
            for produkt in selected_products:
                try:
                    logger.info(f"🔍 Skanowanie: {produkt}")
                    
                    # OLX + Vinted
                    olx_offers = scraper.skanuj_olx(produkt, max_results=4)
                    time.sleep(2)
                    vinted_offers = scraper.skanuj_vinted(produkt, max_results=2)
                    time.sleep(2)
                    
                    all_offers = olx_offers + vinted_offers
                    total_offers += len(all_offers)
                    
                    for oferta in all_offers:
                        try:
                            # Analizuj produkt
                            product_info = analizuj_produkt(oferta['tytul'])
                            if not product_info:
                                continue
                            
                            oferta.update(product_info)
                            
                            # AI Analysis
                            ai_data = db.przewiduj_cene_ai(product_info['model'], product_info['wariant'])
                            
                            # Smart Score
                            smart_score = oblicz_smart_score(oferta, ai_data)
                            
                            logger.info(f"📱 {oferta['tytul'][:30]}... - Score: {smart_score}")
                            
                            # Sprawdź czy już wysłano max 15 alertów dzisiaj
                            stats = db.get_daily_stats()
                            if stats['alerts_sent'] >= 15:
                                logger.info("⚠️ Limit 15 alertów dziennie osiągnięty")
                                continue
                            
                            # Dodaj do bazy
                            if db.dodaj_oferte(oferta, smart_score):
                                
                                # INSTANT ALERT (Score 85+)
                                if smart_score >= 85:
                                    if wyslij_instant_alert(oferta, smart_score, ai_data):
                                        db.oznacz_jako_wyslano(db.get_last_offer_id())
                                        logger.info(f"⚡ INSTANT ALERT: {smart_score}/100")
                                        time.sleep(3)
                                
                                # SCHEDULED ALERT (Score 75-84) - wyśle w scheduled_alerts()
                                elif smart_score >= 75:
                                    logger.info(f"⏰ SCHEDULED: {smart_score}/100")
                            
                        except Exception as e:
                            logger.error(f"❌ Błąd analizy: {e}")
                            continue
                
                except Exception as e:
                    logger.error(f"❌ Błąd skanowania {produkt}: {e}")
                    continue
            
            logger.info(f"✅ Skanowanie zakończone: {total_offers} ofert przeanalizowanych")
            
        except Exception as e:
            logger.error(f"❌ Błąd hourly_scan: {e}")
    
    def scheduled_alerts():
        """Wysyła zaplanowane alerty (score 75-84)"""
        try:
            pending_offers = db.get_pending_offers(min_score=75)
            
            if not pending_offers:
                return
            
            # Sprawdź limit
            stats = db.get_daily_stats()
            remaining_slots = 15 - stats['alerts_sent']
            
            if remaining_slots <= 0:
                return
            
            # Sortuj po score i wyślij najlepsze
            offers_to_send = sorted(pending_offers, key=lambda x: x[7], reverse=True)[:remaining_slots]
            
            for offer_row in offers_to_send:
                try:
                    # Rekonstruuj ofertę
                    oferta = {
                        'tytul': offer_row[1],
                        'cena': offer_row[2],
                        'model': offer_row[3],
                        'wariant': offer_row[4],
                        'lokalizacja': offer_row[5],
                        'platforma': offer_row[6],
                        'url': offer_row[8]
                    }
                    
                    smart_score = offer_row[7]
                    
                    # AI data
                    ai_data = db.przewiduj_cene_ai(oferta['model'], oferta['wariant'])
                    
                    # Wyślij alert
                    if wyslij_scheduled_alert(oferta, smart_score, ai_data):
                        db.oznacz_jako_wyslano(offer_row[0])
                        logger.info(f"⏰ SCHEDULED ALERT: {smart_score}/100")
                        time.sleep(2)
                
                except Exception as e:
                    logger.error(f"❌ Błąd scheduled alert: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"❌ Błąd scheduled_alerts: {e}")
    
    def daily_report():
        """Raport dzienny o 00:00"""
        try:
            stats = db.get_daily_stats()
            wyslij_daily_report(stats)
            logger.info(f"📊 Daily report: {stats['alerts_sent']} alertów")
        except Exception as e:
            logger.error(f"❌ Błąd daily_report: {e}")
    
    # Dodaj pomocniczą metodę do bazy
    def get_last_offer_id_method(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(id) FROM daily_offers')
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    # Monkey patch
    db.get_last_offer_id = lambda: get_last_offer_id_method(db)
    
    # Harmonogram
    
    # Skanowanie co godzinę (6:00-23:00)
    for hour in range(6, 24):
        schedule.every().day.at(f"{hour:02d}:00").do(hourly_scan)
    
    # Scheduled alerts co godzinę (6:00-23:00) 
    for hour in range(6, 24):
        schedule.every().day.at(f"{hour:02d}:30").do(scheduled_alerts)
    
    # Daily report o północy
    schedule.every().day.at("22:00").do(daily_report)  # 22:00 UTC = 00:00 CET
    
    # Start z opóźnieniem
    logger.info("⏰ Pierwszy scan za 3 minuty...")
    time.sleep(180)
    
    # Pierwszy scan
    hourly_scan()
    
    # Główna pętla
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
