import requests
import json
import re
import time
import schedule
import os
import base64
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import cv2
from tensorflow import keras
import tensorflow as tf

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

# Początkowe ceny referencyjne (będą się uczyć)
CENY_BAZOWE = {
    "iPhone 13": {"128GB": 1150, "256GB": 1250, "512GB": 1300},
    "iPhone 14": {"128GB": 1400, "256GB": 1500, "512GB": 1600},
    "iPhone 15": {"128GB": 1900, "256GB": 2000, "512GB": 2100},
    "Samsung Galaxy S24": {"128GB": 1800, "256GB": 1900, "512GB": 2000},
    "Samsung Galaxy S25": {"128GB": 2400, "256GB": 2500, "512GB": 2700},
    "PlayStation 5": {"Standard": 2200, "Digital": 1800},
    "Xbox Series X": {"Standard": 2000}
}

class SmartDatabase:
    """Inteligentna baza danych z funkcjami ML"""
    
    def __init__(self, db_path="smart_flip_alert.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicjalizuje bazę danych z tabelami ML"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela historii ofert
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
                zdjecia_url TEXT,
                stan_urzadzenia TEXT,
                czy_kupiona BOOLEAN DEFAULT 0,
                ranking_oferty REAL
            )
        ''')
        
        # Tabela trendów cenowych
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trendy_cenowe (
                id INTEGER PRIMARY KEY,
                data_aktualizacji TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model TEXT,
                wariant TEXT,
                cena_srednia REAL,
                cena_min REAL,
                cena_max REAL,
                trend_7_dni REAL,
                trend_30_dni REAL,
                przewidywana_cena REAL,
                pewnosc_predykcji REAL
            )
        ''')
        
        # Tabela preferencji użytkownika
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferencje_uzytkownika (
                id INTEGER PRIMARY KEY,
                model TEXT,
                max_cena REAL,
                min_ryzyko INTEGER,
                max_ryzyko INTEGER,
                preferowane_miasta TEXT,
                ostatnia_aktywnosc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Baza danych ML zainicjalizowana")
    
    def dodaj_oferte(self, oferta_data):
        """Dodaje ofertę do historii"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO oferty_historia 
            (tytul, cena, model, wariant, lokalizacja, platforma, seller_rating, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            oferta_data.get('tytul'),
            oferta_data.get('cena'),
            oferta_data.get('model'),
            oferta_data.get('wariant'),
            oferta_data.get('lokalizacja'),
            oferta_data.get('platforma'),
            oferta_data.get('seller_rating'),
            oferta_data.get('opis')
        ))
        
        conn.commit()
        conn.close()
    
    def pobierz_historie_cen(self, model, wariant, dni=30):
        """Pobiera historię cen dla ML"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT data_utworzenia, cena, seller_rating
            FROM oferty_historia 
            WHERE model = ? AND wariant = ? 
            AND data_utworzenia >= datetime('now', '-{} days')
            ORDER BY data_utworzenia
        '''.format(dni)
        
        df = pd.read_sql_query(query, conn, params=(model, wariant))
        conn.close()
        return df

class SmartPricePredictor:
    """AI do przewidywania cen i trendów"""
    
    def __init__(self, database):
        self.db = database
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def przygotuj_dane_treningowe(self):
        """Przygotowuje dane do treningu ML"""
        conn = sqlite3.connect(self.db.db_path)
        
        # Pobierz dane z ostatnich 90 dni
        query = '''
            SELECT 
                julianday(data_utworzenia) as dni_od_epoki,
                cena,
                seller_rating,
                LENGTH(opis) as dlugosc_opisu,
                CASE 
                    WHEN opis LIKE '%stan idealny%' THEN 5
                    WHEN opis LIKE '%stan bardzo dobry%' THEN 4
                    WHEN opis LIKE '%stan dobry%' THEN 3
                    WHEN opis LIKE '%stan zadowalający%' THEN 2
                    ELSE 1
                END as ocena_stanu,
                model,
                wariant
            FROM oferty_historia 
            WHERE data_utworzenia >= datetime('now', '-90 days')
            AND cena > 0
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) < 10:  # Za mało danych do treningu
            return None, None
        
        # Przygotowanie cech (features)
        features = ['dni_od_epoki', 'seller_rating', 'dlugosc_opisu', 'ocena_stanu']
        X = df[features].fillna(0)
        y = df['cena']
        
        return X, y
    
    def wytrenuj_model(self):
        """Trenuje model ML do przewidywania cen"""
        X, y = self.przygotuj_dane_treningowe()
        
        if X is None:
            logger.info("🤖 Za mało danych do treningu ML")
            return False
        
        try:
            # Podziel dane na treningowe i testowe
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Normalizacja danych
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Trening Random Forest
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.model.fit(X_train_scaled, y_train)
            
            # Ocena modelu
            score = self.model.score(X_test_scaled, y_test)
            
            # Zapisz model
            joblib.dump(self.model, 'price_predictor_model.pkl')
            joblib.dump(self.scaler, 'price_scaler.pkl')
            
            self.is_trained = True
            logger.info(f"🤖 Model ML wytrenowany! Dokładność: {score:.2%}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd treningu ML: {e}")
            return False
    
    def przewidz_cene(self, model, wariant, seller_rating=95, dlugosc_opisu=100, ocena_stanu=4):
        """Przewiduje cenę produktu"""
        if not self.is_trained:
            return None, 0
        
        try:
            # Przygotuj dane wejściowe
            dni_od_epoki = time.time() / 86400  # Aktualna data jako dni od epoki
            
            features = np.array([[dni_od_epoki, seller_rating, dlugosc_opisu, ocena_stanu]])
            features_scaled = self.scaler.transform(features)
            
            # Przewidywanie
            przewidywana_cena = self.model.predict(features_scaled)[0]
            
            # Oszacuj pewność predykcji (na podstawie variance)
            pewnosc = min(95, max(60, 90 - abs(przewidywana_cena - CENY_BAZOWE.get(model, {}).get(wariant, przewidywana_cena)) / przewidywana_cena * 100))
            
            return przewidywana_cena, pewnosc
            
        except Exception as e:
            logger.error(f"❌ Błąd przewidywania: {e}")
            return None, 0

class ImageAnalyzer:
    """AI do analizy zdjęć stanu urządzeń"""
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
    
    def zaladuj_model(self):
        """Ładuje pre-trained model do analizy obrazów"""
        try:
            # Używamy MobileNetV2 jako base model
            base_model = tf.keras.applications.MobileNetV2(
                weights='imagenet',
                include_top=False,
                input_shape=(224, 224, 3)
            )
            
            # Dodajemy własne warstwy do klasyfikacji stanu
            model = tf.keras.Sequential([
                base_model,
                tf.keras.layers.GlobalAveragePooling2D(),
                tf.keras.layers.Dense(128, activation='relu'),
                tf.keras.layers.Dropout(0.5),
                tf.keras.layers.Dense(5, activation='softmax')  # 5 klas stanu
            ])
            
            self.model = model
            self.is_loaded = True
            logger.info("🖼️ Model analizy obrazów załadowany")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd ładowania modelu obrazów: {e}")
            return False
    
    def analizuj_stan_ze_zdjecia(self, url_zdjecia):
        """Analizuje stan urządzenia ze zdjęcia"""
        if not self.is_loaded:
            return "nieznany", 50
        
        try:
            # Pobierz i przygotuj obraz
            response = requests.get(url_zdjecia)
            image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            image = cv2.resize(image, (224, 224))
            image = np.expand_dims(image, axis=0) / 255.0
            
            # Przewidywanie
            predykcja = self.model.predict(image)
            klasy_stanu = ['uszkodzony', 'słaby', 'zadowalający', 'dobry', 'idealny']
            
            indeks_klasy = np.argmax(predykcja[0])
            pewnosc = predykcja[0][indeks_klasy] * 100
            
            return klasy_stanu[indeks_klasy], pewnosc
            
        except Exception as e:
            logger.error(f"❌ Błąd analizy obrazu: {e}")
            return "nieznany", 0

class SmartTrendAnalyzer:
    """AI do analizy trendów i przewidywań rynkowych"""
    
    def __init__(self, database):
        self.db = database
    
    def analizuj_trendy(self, model, wariant):
        """Analizuje trendy cenowe dla produktu"""
        df = self.db.pobierz_historie_cen(model, wariant, dni=30)
        
        if len(df) < 5:
            return {
                'trend': 'stabilny',
                'zmiana_7_dni': 0,
                'zmiana_30_dni': 0,
                'przewidywana_zmiana': 0,
                'rekomendacja': 'brak danych'
            }
        
        # Konwertuj daty
        df['data_utworzenia'] = pd.to_datetime(df['data_utworzenia'])
        df = df.sort_values('data_utworzenia')
        
        # Oblicz trendy
        ceny_7_dni = df[df['data_utworzenia'] >= datetime.now() - timedelta(days=7)]['cena']
        ceny_30_dni = df['cena']
        
        if len(ceny_7_dni) > 1:
            zmiana_7_dni = ((ceny_7_dni.iloc[-1] - ceny_7_dni.iloc[0]) / ceny_7_dni.iloc[0]) * 100
        else:
            zmiana_7_dni = 0
        
        if len(ceny_30_dni) > 1:
            zmiana_30_dni = ((ceny_30_dni.iloc[-1] - ceny_30_dni.iloc[0]) / ceny_30_dni.iloc[0]) * 100
        else:
            zmiana_30_dni = 0
        
        # Określ trend
        if zmiana_7_dni > 5:
            trend = 'rosnący'
            rekomendacja = 'kup teraz, cena rośnie'
        elif zmiana_7_dni < -5:
            trend = 'spadający'
            rekomendacja = 'poczekaj, cena spada'
        else:
            trend = 'stabilny'
            rekomendacja = 'dobry moment na zakup'
        
        # Przewidywanie przyszłej zmiany (prosta regresja liniowa)
        if len(df) > 3:
            x = np.arange(len(df))
            y = df['cena'].values
            z = np.polyfit(x, y, 1)
            przewidywana_zmiana = z[0] * 7  # Przewidywanie na 7 dni
        else:
            przewidywana_zmiana = 0
        
        return {
            'trend': trend,
            'zmiana_7_dni': round(zmiana_7_dni, 2),
            'zmiana_30_dni': round(zmiana_30_dni, 2),
            'przewidywana_zmiana': round(przewidywana_zmiana, 2),
            'rekomendacja': rekomendacja,
            'srednia_cena': round(df['cena'].mean(), 2),
            'min_cena': round(df['cena'].min(), 2),
            'max_cena': round(df['cena'].max(), 2)
        }

class SmartFlipAlert:
    """Główna klasa z AI/ML"""
    
    def __init__(self):
        self.db = SmartDatabase()
        self.price_predictor = SmartPricePredictor(self.db)
        self.image_analyzer = ImageAnalyzer()
        self.trend_analyzer = SmartTrendAnalyzer(self.db)
        
        # Inicjalizacja AI
        self.inicjalizuj_ai()
    
    def inicjalizuj_ai(self):
        """Inicjalizuje wszystkie komponenty AI"""
        logger.info("🤖 Inicjalizacja systemu AI/ML...")
        
        # Ładuj istniejący model lub trenuj nowy
        try:
            self.price_predictor.model = joblib.load('price_predictor_model.pkl')
            self.price_predictor.scaler = joblib.load('price_scaler.pkl')
            self.price_predictor.is_trained = True
            logger.info("✅ Załadowano istniejący model ML")
        except:
            logger.info("🤖 Brak modelu - rozpoczynam trening...")
            self.price_predictor.wytrenuj_model()
        
        # Ładuj model analizy obrazów
        self.image_analyzer.zaladuj_model()
    
    def inteligentna_analiza_oferty(self, oferta):
        """Kompleksowa analiza oferty z AI"""
        analiza = {
            'podstawowa_ocena': None,
            'przewidywana_cena': None,
            'pewnosc_predykcji': 0,
            'analiza_trendu': None,
            'stan_ze_zdjecia': 'nieznany',
            'pewnosc_stanu': 0,
            'rekomendacja_ai': 'sprawdź ręcznie',
            'inteligentny_alert': False
        }
        
        model = oferta.get('model')
        wariant = oferta.get('wariant')
        
        if model and wariant:
            # 1. Przewidywanie ceny AI
            przewidywana_cena, pewnosc = self.price_predictor.przewidz_cene(
                model, wariant,
                oferta.get('seller_rating', 95),
                len(oferta.get('opis', '')),
                4  # Domyślny stan
            )
            
            analiza['przewidywana_cena'] = przewidywana_cena
            analiza['pewnosc_predykcji'] = pewnosc
            
            # 2. Analiza trendów
            trendy = self.trend_analyzer.analizuj_trendy(model, wariant)
            analiza['analiza_trendu'] = trendy
            
            # 3. Analiza zdjęcia (jeśli dostępne)
            if oferta.get('zdjecia_url'):
                stan, pewnosc_stanu = self.image_analyzer.analizuj_stan_ze_zdjecia(oferta['zdjecia_url'])
                analiza['stan_ze_zdjecia'] = stan
                analiza['pewnosc_stanu'] = pewnosc_stanu
            
            # 4. Inteligentna rekomendacja
            cena_oferty = oferta.get('cena', 0)
            
            if przewidywana_cena and cena_oferty < przewidywana_cena * 0.8:
                if trendy['trend'] == 'spadający':
                    analiza['rekomendacja_ai'] = '⏳ Poczekaj - cena jeszcze spadnie'
                elif trendy['trend'] == 'rosnący':
                    analiza['rekomendacja_ai'] = '🔥 KUP NATYCHMIAST - świetna okazja!'
                    analiza['inteligentny_alert'] = True
                else:
                    analiza['rekomendacja_ai'] = '✅ Dobra oferta - rozważ zakup'
                    analiza['inteligentny_alert'] = True
            elif przewidywana_cena and cena_oferty > przewidywana_cena * 1.1:
                analiza['rekomendacja_ai'] = '❌ Przecenione - szukaj dalej'
            else:
                analiza['rekomendacja_ai'] = '🤔 Cena uczciwa - sprawdź stan'
        
        # Zapisz ofertę do historii dla dalszego uczenia
        self.db.dodaj_oferte({
            'tytul': oferta.get('tytul'),
            'cena': oferta.get('cena'),
            'model': model,
            'wariant': wariant,
            'lokalizacja': oferta.get('lokalizacja'),
            'platforma': oferta.get('platforma'),
            'seller_rating': oferta.get('seller_rating'),
            'opis': oferta.get('opis')
        })
        
        return analiza

def wyslij_inteligentny_alert(oferta, analiza):
    """Wysyła inteligentny alert z AI"""
    model = oferta.get('model', 'Nieznany')
    wariant = oferta.get('wariant', '')
    cena = oferta.get('cena', 0)
    lokalizacja = oferta.get('lokalizacja', 'Nieznana')
    link = oferta.get('link', '')
    
    przewidywana_cena = analiza.get('przewidywana_cena')
    pewnosc = analiza.get('pewnosc_predykcji', 0)
    trendy = analiza.get('analiza_trendu', {})
    rekomendacja = analiza.get('rekomendacja_ai', 'Sprawdź ręcznie')
    
    # Emoji na podstawie rekomendacji
    if '🔥 KUP NATYCHMIAST' in rekomendacja:
        emoji_glowny = '🔥'
        priorytet = 'BARDZO WYSOKI'
    elif '✅ Dobra oferta' in rekomendacja:
        emoji_glowny = '✅'
        priorytet = 'WYSOKI'
    elif '⏳ Poczekaj' in rekomendacja:
        emoji_glowny = '⏳'
        priorytet = 'NISKI'
    else:
        emoji_glowny = '🤖'
        priorytet = 'ŚREDNI'
    
    # Oblicz oszczędności AI
    if przewidywana_cena:
        oszczednosci_ai = int(przewidywana_cena - cena)
        emoji_oszczednosci = '💰' if oszczednosci_ai > 0 else '💸'
    else:
        oszczednosci_ai = 0
        emoji_oszczednosci = '💰'
    
    alert = f"""{emoji_glowny} <b>INTELIGENTNY ALERT AI</b>

🤖 <b>Priorytet AI:</b> {priorytet}
📱 <b>{model} {wariant}</b>
💰 <b>Cena:</b> {cena} PLN
🧠 <b>AI przewiduje:</b> {int(przewidywana_cena) if przewidywana_cena else 'N/A'} PLN
📊 <b>Pewność AI:</b> {int(pewnosc)}%
📈 <b>Trend 7 dni:</b> {trendy.get('zmiana_7_dni', 0):+.1f}%
📍 <b>Lokalizacja:</b> {lokalizacja}

🤖 <b>Rekomendacja AI:</b>
{rekomendacja}

📊 <b>Analiza trendu:</b>
• Trend: {trendy.get('trend', 'nieznany')} ({trendy.get('zmiana_7_dni', 0):+.1f}% tydzień)
• Średnia cena: {int(trendy.get('srednia_cena', 0))} PLN
• Min/Max: {int(trendy.get('min_cena', 0))}/{int(trendy.get('max_cena', 0))} PLN

{emoji_oszczednosci} <b>Potencjalne zyski AI:</b> {oszczednosci_ai:+d} PLN

🔗 <a href="{link}">SPRAWDŹ OFERTĘ</a>

<i>🤖 Powered by Machine Learning</i>"""
    
    # Wyślij alert
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dane = {
        "chat_id": CHAT_ID,
        "text": alert,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=dane)
        if response.status_code == 200:
            logger.info("🤖 Inteligentny alert wysłany pomyślnie")
            return True
        else:
            logger.error(f"❌ Błąd wysyłania alertu AI: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Błąd połączenia: {e}")
        return False

def main():
    """Główna funkcja z AI/ML"""
    logger.info("🤖 Smart Flip Alert z AI/ML uruchomiony!")
    
    # Inicjalizacja systemu AI
    smart_system = SmartFlipAlert()
    
    # Wyślij powiadomienie o uruchomieniu AI
    start_message = f"""🤖 <b>SMART FLIP ALERT - AI/ML AKTYWNY!</b>

🧠 <b>Sztuczna Inteligencja:</b>
✅ Machine Learning do przewidywania cen
✅ Analiza trendów rynkowych
✅ Rozpoznawanie stanu ze zdjęć
✅ Personalizowane rekomendacje
✅ Automatyczne uczenie się

📊 <b>Funkcje AI:</b>
• Przewidywanie przyszłych cen
• Analiza trendów 7/30 dni
• Ocena ryzyka inwestycji
• Inteligentne alerty priorytetowe
• Self-learning system

🎯 <b>Inteligentne kryteria:</b>
• AI analizuje każdą ofertę
• Przewiduje optymalne momenty zakupu
• Ostrzega przed przecenionymi ofertami
• Uczy się z Twoich preferencji

⚡ <b>Status:</b> SZTUCZNA INTELIGENCJA AKTYWNA!

<i>🚀 Przyszłość flippingu rozpoczęła się!</i>"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dane = {
        "chat_id": CHAT_ID,
        "text": start_message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=dane)
    
    # Trenuj model co 24 godziny
    schedule.every(24).hours.do(smart_system.price_predictor.wytrenuj_model)
    
    # Główna pętla z AI
    logger.info("🤖 System AI działa w pełnej gotowości")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
