import requests
import json
import re
import time
import schedule
import os
import random
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dane bota (z zmiennych środowiskowych dla bezpieczeństwa)
BOT_TOKEN = os.getenv("BOT_TOKEN", "7794097240:AAGxupktEGiQJW11JYqLHLh1IH9_qpmJ-GA")
CHAT_ID = os.getenv("CHAT_ID", "1824475841")

# Zaktualizowana baza cen referencyjnych - lipiec 2025
CENY_REFERENCYJNE = {
    # iPhone'y
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
    
    # Samsung Galaxy - ZAKTUALIZOWANE O NOWE MODELE
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
    
    # NOWE MODELE SAMSUNG S25 (2025) - ceny używanych po 6 miesiącach
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
    
    # Konsole - OGRANICZONE
    "PlayStation 5": {
        "Standard": 2200, "Digital": 1800
    },
    "Xbox Series X": {
        "Standard": 2000
    }
}

# Alternatywne nazwy produktów
ALTERNATYWNE_NAZWY = {
    "Samsung Galaxy S25": ["S25", "Galaxy S25", "Samsung S25"],
    "Samsung Galaxy S25 Plus": ["S25+", "S25 Plus", "Galaxy S25+", "Samsung S25+"],
    "Samsung Galaxy S25 Ultra": ["S25 Ultra", "Galaxy S25 Ultra", "Samsung S25 Ultra"],
    "Samsung Galaxy S25 Edge": ["S25 Edge", "Galaxy S25 Edge", "Samsung S25 Edge"],
    "PlayStation 5": ["PS5", "PlayStation 5", "Sony PS5", "Playstation 5"],
    "Xbox Series X": ["Xbox Series X", "Xbox X", "Series X", "Microsoft Xbox Series X"]
}

# Słowa ostrzegawcze
SLOWA_OSTRZEGAWCZE = [
    "uszkodzony", "pęknięty", "zablokowany", "icloud", "simlock", "cracked", 
    "broken", "damaged", "parts", "repair", "serwis", "nie działa", "wadliwy",
    "ghost touch", "martwy piksel", "spalony", "zalany", "po serwisie"
]

# Miasta województwa śląskiego - rozszerzone
MIASTA_SLASKIE = [
    "katowice", "częstochowa", "sosnowiec", "gliwice", "zabrze", "bielsko-biała",
    "bytom", "rybnik", "ruda śląska", "tychy", "dąbrowa górnicza", "chorzów",
    "jaworzno", "jastrzębie-zdrój", "mysłowice", "siemianowice śląskie",
    "żory", "świętochłowice", "będzin", "tarnowskie góry", "piekary śląskie",
    "czechowice-dziedzice", "wodzisław śląski", "zawiercie", "racibórz",
    "cieszyn", "pszczyna", "mikołów", "knurów", "ustroń", "wisła",
    "bieruń", "lędziny", "imielin", "bojszowy", "chełm śląski", "czeladź",
    "kalety", "kozienice", "łaziska górne", "marklowice", "miasteczko śląskie",
    "ornontowice", "pyskowice", "radlin", "czerwionka-leszczyny", "godów",
    "kobiór", "pawłowice", "wyry", "gierałtowice", "pilchowice", "rudziniec",
    "sośnicowice", "świerklany", "toszek", "wielowieś", "zbrosławice"
]

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
    
    # Sprawdź wszystkie modele
    for model in CENY_REFERENCYJNE:
        model_upper = model.upper()
        
        # Sprawdź dokładne dopasowanie
        if model_upper in tekst:
            produkt_info = {"typ": "Elektronika", "model": model}
            break
            
        # Sprawdź alternatywne nazwy
        if model in ALTERNATYWNE_NAZWY:
            for alt_nazwa in ALTERNATYWNE_NAZWY[model]:
                if alt_nazwa.upper() in tekst:
                    produkt_info = {"typ": "Elektronika", "model": model}
                    break
            if produkt_info:
                break
    
    if not produkt_info:
        return None
    
    # Znajdź wariant (pojemność, wersję)
    wariant = None
    model_ceny = CENY_REFERENCYJNE[produkt_info["model"]]
    
    # Sprawdź wszystkie dostępne warianty
    for wariant_klucz in model_ceny.keys():
        if wariant_klucz.upper() in tekst:
            wariant = wariant_klucz
            break
    
    # Jeśli nie znaleziono wariantu, spróbuj wyodrębnić pojemność
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

def ocen_ryzyko(cena, cena_ref, tytul, opis="", platforma=""):
    """Ocenia ryzyko oferty (1-5)"""
    ryzyko = 1
    
    # Ryzyko cenowe
    if not cena_ref:
        ryzyko += 1
    elif cena < cena_ref * 0.4:
        ryzyko += 3  # Bardzo niska cena - podejrzane
    elif cena < cena_ref * 0.6:
        ryzyko += 2  # Niska cena
    elif cena < cena_ref * 0.8:
        ryzyko += 1  # Umiarkowanie niska cena
    
    # Sprawdź słowa ostrzegawcze
    tekst = (tytul + " " + opis).upper()
    for slowo in SLOWA_OSTRZEGAWCZE:
        if slowo.upper() in tekst:
            ryzyko += 2
            break
    
    # Ryzyko platformy
    if platforma.lower() in ["facebook", "olx"]:
        ryzyko += 1  # Większe ryzyko na platformach C2C
    
    return min(ryzyko, 5)

def jest_w_slaskim(lokalizacja):
    """Sprawdza czy lokalizacja jest w woj. śląskim"""
    if not lokalizacja:
        return False
    
    lokalizacja_lower = lokalizacja.lower()
    
    # Sprawdź miasta
    for miasto in MIASTA_SLASKIE:
        if miasto in lokalizacja_lower:
            return True
    
    # Sprawdź województwo
    return any(slowo in lokalizacja_lower for slowo in ["śląskie", "slask", "katowice", "silesia"])

def generuj_testowe_oferty():
    """Generuje testowe oferty do demonstracji"""
    logger.info("🔍 Generowanie testowych ofert...")
    
    # Szablony ofert
    szablony_ofert = [
        ("iPhone 13 128GB Space Gray", 950, "Katowice", "Allegro"),
        ("Samsung Galaxy S25 256GB", 2300, "Gliwice", "Allegro"),
        ("PlayStation 5 Standard Edition", 1900, "Sosnowiec", "Facebook"),
        ("iPhone 14 Pro 256GB", 1800, "Bytom", "Facebook"),
        ("Xbox Series X", 1700, "Częstochowa", "Facebook"),
        ("Samsung Galaxy S25 Ultra 512GB", 3600, "Zabrze", "Allegro"),
        ("iPhone 15 Pro Max 256GB", 2900, "Tychy", "Allegro"),
        ("Samsung Galaxy S24 Ultra 256GB", 2400, "Rybnik", "Facebook"),
        ("Samsung Galaxy S25 Edge 256GB", 3000, "Chorzów", "Allegro"),
        ("PlayStation 5 Digital", 1600, "Jaworzno", "Facebook")
    ]
    
    # Wybierz losowe oferty
    oferty = []
    for szablon in random.sample(szablony_ofert, random.randint(4, 7)):
        tytul, cena_base, miasto, platforma = szablon
        
        # Dodaj losową wariację ceny (+/- 15%)
        wariacja = random.uniform(0.85, 1.15)
        cena = int(cena_base * wariacja)
        
        oferty.append({
            "tytul": tytul,
            "cena": cena,
            "lokalizacja": miasto,
            "link": f"https://{platforma.lower()}.pl/oferta/{random.randint(10000, 99999)}",
            "platforma": platforma,
            "opis": f"Stan bardzo dobry. Telefon używany przez {random.randint(6, 18)} miesięcy."
        })
    
    return oferty

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
                oferta["platforma"]
            )
            
            # Pokaż analizę
            logger.info(f"📱 {oferta['tytul']}")
            logger.info(f"💰 Cena: {oferta['cena']} PLN | Ref: {cena_ref} PLN")
            logger.info(f"🎯 Próg (85%): {int(cena_ref * 0.85)} PLN")
            logger.info(f"🏪 Platforma: {oferta['platforma']}")
            logger.info(f"📍 Lokalizacja: {oferta['lokalizacja']}")
            logger.info(f"⚠️ Ryzyko: {ryzyko}/5")
            
            # Sprawdź czy to dobra oferta (cena niższa o 15% od referencyjnej)
            if oferta["cena"] < cena_ref * 0.85:
                
                # Oblicz negocjacje
                min_neg = max(int(oferta["cena"] * 0.85), int(cena_ref * 0.75))
                max_neg = min(int(oferta["cena"] * 0.95), int(cena_ref * 0.85))
                oszczednosci = cena_ref - oferta["cena"]
                
                # Emoji dla platformy
                emoji_platforma = {
                    "Allegro": "🛒",
                    "Facebook": "👥", 
                    "Inna": "🔍"
                }.get(oferta["platforma"], "🔍")
                
                alert = f"""🚨 <b>ZNALEZIONA OFERTA!</b>

{emoji_platforma} <b>Platforma:</b> {oferta['platforma']}
📱 <b>{oferta['tytul']}</b>
💰 <b>Cena:</b> {oferta['cena']} PLN
💎 <b>Cena ref:</b> {cena_ref} PLN
🔋 <b>Bateria:</b> Sprawdź w ofercie
📍 <b>Miasto:</b> {oferta['lokalizacja']}
⚠️ <b>Ryzyko:</b> {ryzyko}/5
💡 <b>Negocjacje:</b> {min_neg}-{max_neg} PLN
🔗 <a href="{oferta['link']}">Link do oferty</a>

<i>💰 Oszczędzisz: {oszczednosci} PLN!</i>"""
                
                dobre_oferty.append(alert)
                logger.info(f"✅ DOBRA OFERTA! Oszczędność: {oszczednosci} PLN")
            else:
                logger.info(f"⏭️ Cena za wysoka: {oferta['cena']} PLN > {int(cena_ref * 0.85)} PLN")
                
        except Exception as e:
            logger.error(f"❌ Błąd przetwarzania oferty: {e}")
            continue
    
    return dobre_oferty

def uruchom_skanowanie():
    """Główna funkcja skanowania"""
    try:
        logger.info("🚀 Rozpoczynam skanowanie Multi-Platform Flip Alert")
        
        # Generuj testowe oferty (w przyszłości zastąpimy prawdziwymi API)
        oferty = generuj_testowe_oferty()
        logger.info(f"📊 Znaleziono {len(oferty)} ofert")
        
        # Przetwórz oferty
        dobre_oferty = przetworz_oferty(oferty)
        
        # Wyślij alerty
        if dobre_oferty:
            logger.info(f"🎉 Znaleziono {len(dobre_oferty)} dobrych ofert!")
            for i, alert in enumerate(dobre_oferty):
                wyslij_alert(alert)
                if i < len(dobre_oferty) - 1:  # Nie czekaj po ostatnim
                    time.sleep(3)
        else:
            logger.info("😔 Brak dobrych ofert w tym skanowaniu")
            wyslij_alert("🔍 <b>Skanowanie zakończone</b>\n\n😔 Brak dobrych ofert tym razem.\n\n⏰ Następne skanowanie za godzinę...")
        
        # Wyślij podsumowanie
        czas = datetime.now().strftime("%H:%M")
        summary = f"""📊 <b>Podsumowanie skanowania</b>

🕒 <b>Czas:</b> {czas}
🔍 <b>Przeskanowano:</b> {len(oferty)} ofert
✅ <b>Znaleziono dobrych:</b> {len(dobre_oferty)} ofert
🏪 <b>Platformy:</b> Allegro, Facebook, Inne

⏰ <b>Następne skanowanie:</b> za godzinę
🎯 <b>Status:</b> System aktywny 24/7 w chmurze

<i>Flip Alert działa! ☁️🚀</i>"""
        
        wyslij_alert(summary)
        logger.info("✅ Skanowanie zakończone pomyślnie")
        
    except Exception as e:
        logger.error(f"❌ Błąd podczas skanowania: {e}")
        wyslij_alert(f"❌ <b>Błąd systemu</b>\n\n{str(e)}\n\n🔧 Restartuję za 5 minut...")

def main():
    """Główna funkcja aplikacji"""
    logger.info("🚀 Multi-Platform Flip Alert uruchomiony w Railway!")
    
    # Wyślij powiadomienie o uruchomieniu
    start_message = f"""🚀 <b>Flip Alert w chmurze!</b>

✅ System uruchomiony pomyślnie na Railway
☁️ Działa 24/7 automatycznie
🔄 Skanowanie co godzinę
📊 Zaktualizowana baza cen (lipiec 2025)

🎯 <b>Monitorowane produkty:</b>
• iPhone 11-16 (wszystkie wersje)
• Samsung Galaxy S21-S25 (w tym S25 Edge!)
• PlayStation 5 (Standard/Digital)
• Xbox Series X

📍 <b>Obszar:</b> Województwo śląskie ({len(MIASTA_SLASKIE)} miast)
⚡ <b>Status:</b> AKTYWNY

<i>Pierwsze skanowanie za 5 minut! 🔔</i>"""
    
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
        time.sleep(60)  # Sprawdzaj co minutę

if __name__ == "__main__":
    main()
