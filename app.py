import os
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, BooleanField, IntegerField, TextAreaField, FileField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import datetime, timedelta
import requests
import difflib
import json
import csv
import io
from werkzeug.utils import secure_filename

import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'tajny_klucz'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  

def pobierz_kurs_waluty(waluta, data=None):
    try:
        if waluta == 'USD':
            kod = 'USD'
        elif waluta == 'EUR':
            kod = 'EUR'
        elif waluta == 'GBP':
            kod = 'GBP'
        else:
            return None
        
        if data:
            if datetime.strptime(data, '%Y-%m-%d') > datetime.now():
                data = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                
            url = f"http://api.nbp.pl/api/exchangerates/rates/a/{kod}/{data}/?format=json"
        else:
            url = f"http://api.nbp.pl/api/exchangerates/rates/a/{kod}/?format=json"
        
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data['rates'][0]['mid']
        elif response.status_code == 404:
            if data:
                data_dt = datetime.strptime(data, '%Y-%m-%d')
                for i in range(1, 7):
                    prev_date = (data_dt - timedelta(days=i)).strftime('%Y-%m-%d')
                    url = f"http://api.nbp.pl/api/exchangerates/rates/a/{kod}/{prev_date}/?format=json"
                    response = requests.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        return data['rates'][0]['mid']
            return None
        return None
    except Exception as e:
        print(f"Błąd przy pobieraniu kursu: {e}")
        return None

@app.route('/toggle_dark_mode', methods=['POST'])
def toggle_dark_mode():
    session['dark_mode'] = not session.get('dark_mode', False)
    session.modified = True
    return jsonify({
        'status': 'success', 
        'dark_mode': session['dark_mode'],
        'icon': '🌞' if session['dark_mode'] else '🌓'
    })

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

# Opcje od 1 do 100 dla mnożnika
mnoznik_choices = [(str(i), f"{i} szt.") for i in range(1, 101)]

kategorie_choices = [
    ('A', 'Supermarket (6,15%)'),
    ('B', 'Cukier (12,92%)'),
    ('C', 'Chemia gospodarcza (12,92%)'),
    ('D', 'AGD zwykłe (13,53%)'),
    ('E', 'Elektronika (5,55%)'),
    ('F', 'Chemia do 60 zł (18,45% / 9,84%)'),
    ('G', 'Sklep internetowy'),
    ('H', 'Inna prowizja'),
    ('I', 'Strefa okazji (+60% prowizji podstawowej)')
]

kategorie_podst_choices = [
    ('A', 'Supermarket (6,15%)'),
    ('B', 'Cukier (12,92%)'),
    ('C', 'Chemia gospodarcza (12,92%)'),
    ('D', 'AGD zwykłe (13,53%)'),
    ('E', 'Elektronika (5,55%)'),
    ('F', 'Chemia do 60 zł (18,45% / 9,84%)'),
    ('H', 'Inna prowizja')
]

class KalkulatorMarzyForm(FlaskForm):
    cena_zakupu = StringField('Cena zakupu:', validators=[DataRequired()])
    mnoznik_zakupu = SelectField('Mnożnik:', choices=mnoznik_choices, default="1", validators=[DataRequired()])
    cena_sprzedazy = StringField('Cena sprzedaży:', validators=[DataRequired()])
    mnoznik_sprzedazy = SelectField('Mnożnik:', choices=mnoznik_choices, default="1", validators=[DataRequired()])
    kategoria = SelectField('Kategoria:', choices=kategorie_choices, validators=[DataRequired()])
    inna_prowizja = StringField('Procent prowizji:')
    kategoria_podstawowa = SelectField('Kategoria podst.:', choices=kategorie_podst_choices, validators=[Optional()])
    ilosc_w_zestawie = StringField('Ilość w zestawie:', default="1", validators=[DataRequired()])
    czy_smart = BooleanField('Czy smart?', default=True)
    kwota_dostawy_smart = StringField('Kwota dostawy:', default="0")
    koszt_pakowania = StringField('Koszt pakowania (zł):', default="0")
    marza_kwota = StringField('Marża minimalna (zł):', default="2")
    marza_procent = StringField('Marża procentowa (%):', default="15")
    submit = SubmitField('Oblicz marżę')

class KalkulatorZakupuForm(FlaskForm):
    cena_sprzedazy_docelowa = StringField('Docelowa cena sprzedaży:', validators=[DataRequired()])
    oczekiwana_marza = StringField('Oczekiwana marża (zł):', default="2", validators=[DataRequired()])
    kategoria_zakup = SelectField('Kategoria:', choices=kategorie_choices, default="A", validators=[DataRequired()])
    inna_prowizja_zakup = StringField('Procent prowizji:')
    kategoria_podstawowa_zakup = SelectField('Kategoria podst.:', choices=kategorie_podst_choices, default="A", validators=[Optional()])
    czy_smart_zakup = BooleanField('Czy smart?', default=True)
    kwota_dostawy_smart_zakup = StringField('Kwota dostawy:', default="0")
    koszt_pakowania_zakup = StringField('Koszt pakowania (zł):', default="0")
    submit_zakup = SubmitField('Oblicz cenę zakupu')

class KalkulatorVATForm(FlaskForm):
    cena_netto = StringField('Wpisz cenę netto:', validators=[DataRequired()])
    vat = SelectField('Wybierz podatek VAT:', choices=[('5', '5%'), ('8', '8%'), ('23', '23%')], default="23", validators=[DataRequired()])
    ilosc_sztuk = IntegerField('Ilość sztuk w cenie netto:', default=1, validators=[NumberRange(min=1)])
    koszt_dostawy_sztuka = StringField('Wpisz koszt dostawy na sztukę:', default="0")
    kwota_dostawy = StringField('Lub wpisz kwotę dostawy:', default="0")
    ilosc_w_dostawie = IntegerField('Ilość sztuk w dostawie:', default=1, validators=[NumberRange(min=1)])
    inna_waluta_towar = BooleanField('Inna waluta niż PLN (towar)', default=False)
    typ_kursu_towar = SelectField('Typ kursu:', choices=[('aktualny', 'Aktualny kurs'), ('historyczny', 'Kurs z dnia'), ('wlasny', 'Własny kurs')], default='aktualny')
    data_kursu_towar = StringField('Data kursu (RRRR-MM-DD):', default=datetime.now().strftime('%Y-%m-%d'))
    waluta_towar = SelectField('Waluta:', choices=[('USD', 'USD (dolar amerykański)'), ('EUR', 'EUR (euro)'), ('GBP', 'GBP (funt brytyjski)')], default='USD')
    kurs_waluty_towar = StringField('Kurs waluty (1 waluta = X PLN):', default="1.0", validators=[Optional()])
    inna_waluta_dostawa = BooleanField('Inna waluta niż PLN (dostawa)', default=False)
    typ_kursu_dostawa = SelectField('Typ kursu:', choices=[('aktualny', 'Aktualny kurs'), ('historyczny', 'Kurs z dnia'), ('wlasny', 'Własny kurs')], default='aktualny')
    data_kursu_dostawa = StringField('Data kursu (RRRR-MM-DD):', default=datetime.now().strftime('%Y-%m-%d'))
    waluta_dostawa = SelectField('Waluta:', choices=[('USD', 'USD (dolar amerykański)'), ('EUR', 'EUR (euro)'), ('GBP', 'GBP (funt brytyjski)')], default='USD')
    kurs_waluty_dostawa = StringField('Kurs waluty (1 waluta = X PLN):', default="1.0", validators=[Optional()])
    submit = SubmitField('Oblicz VAT')

class KalkulatorZbiorczyForm(FlaskForm):
    plik_csv = FileField('Prześlij plik CSV:')
    kategoria_zbiorcza = SelectField('Kategoria:', choices=kategorie_choices, default="A", validators=[DataRequired()])
    czy_smart_zbiorcze = BooleanField('Czy smart?', default=True)
    koszt_pakowania_zbiorcze = StringField('Koszt pakowania na sztukę (zł):', default="0")
    submit_zbiorczy = SubmitField('Oblicz marże zbiorczo')

def zamien_przecinek_na_kropke(liczba):
    if isinstance(liczba, str):
        liczba = liczba.replace(",", ".")
        try:
            return float(liczba)
        except ValueError:
            return 0.0
    return float(liczba) if liczba else 0.0

def przetworz_dane_zbiorcze(plik_csv, kategoria, czy_smart, koszt_pakowania):
    try:
        if not plik_csv or plik_csv.filename == '':
            return None, "Nie wybrano pliku"
        content_bytes = plik_csv.read()
        if not content_bytes:
            return None, "Plik jest pusty"
        
        content_str = None
        for encoding in ['utf-8-sig', 'utf-8', 'cp1250', 'iso-8859-2', 'windows-1250', 'latin1']:
            try:
                content_str = content_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if content_str is None:
            content_str = content_bytes.decode('utf-8', errors='replace')
        
        content_str = content_str.replace('\r\n', '\n').replace('\r', '\n')
        lines = content_str.strip().split('\n')
        if not lines:
            return None, "Plik nie zawiera danych"
        
        has_data = False
        for line in lines:
            if line.strip() and any(c.isdigit() for c in line):
                has_data = True
                break
        if not has_data:
            return None, "Plik nie zawiera danych liczbowych"
        
        first_line = lines[0]
        if ';' in first_line: delimiter = ';'
        elif ',' in first_line: delimiter = ','
        elif '\t' in first_line: delimiter = '\t'
        else:
            for line in lines[1:]:
                if line.strip():
                    if ';' in line: delimiter = ';'
                    elif ',' in line: delimiter = ','
                    elif '\t' in line: delimiter = '\t'
                    else: delimiter = ';'
                    break
        
        csv_data = io.StringIO(content_str)
        reader = csv.reader(csv_data, delimiter=delimiter)
        rows = list(reader)
        if not rows: return None, "Brak wierszy w pliku"
        
        has_headers = False
        first_row = rows[0]
        header_candidates = ['nazwa', 'produkt', 'cena', 'netto', 'brutto', 'lp', 'nr', 'nazwa produktu']
        for cell in first_row:
            if cell and isinstance(cell, str):
                if any(header in cell.lower().strip() for header in header_candidates):
                    has_headers = True
                    break
        
        produkty = []
        start_row = 1 if has_headers else 0
        for row_num, row in enumerate(rows[start_row:], start=1):
            if not row or all(not cell for cell in row): continue
            row = [str(cell).strip() if cell is not None else '' for cell in row]
            
            cena_netto = cena_brutto = None
            nazwa = ""
            lp = str(row_num)
            
            if has_headers:
                for col_num, (header, value) in enumerate(zip(first_row, row)):
                    if not header or not value: continue
                    header_lower = header.lower().strip()
                    value_clean = value.strip()
                    if not value_clean: continue
                    
                    if 'lp' in header_lower or 'l.p' in header_lower or 'nr' in header_lower or 'id' in header_lower: lp = value_clean
                    elif 'nazwa' in header_lower or 'produkt' in header_lower or 'product' in header_lower: nazwa = value_clean
                    elif 'netto' in header_lower and ('brutto' not in header_lower):
                        try:
                            cleaned = value_clean.replace('zł', '').replace('pln', '').replace(' ', '').replace(',', '.')
                            cena_netto = float(cleaned)
                        except (ValueError, TypeError): cena_netto = None
                    elif 'brutto' in header_lower:
                        try:
                            cleaned = value_clean.replace('zł', '').replace('pln', '').replace(' ', '').replace(',', '.')
                            cena_brutto = float(cleaned)
                        except (ValueError, TypeError): cena_brutto = None
                    elif 'cena' in header_lower and cena_netto is None and cena_brutto is None:
                        try:
                            cleaned = value_clean.replace('zł', '').replace('pln', '').replace(' ', '').replace(',', '.')
                            cena_brutto = float(cleaned)
                        except (ValueError, TypeError): cena_brutto = None
            else:
                for col_num, value in enumerate(row):
                    if not value: continue
                    value_clean = value.strip()
                    if col_num == 0 and value_clean.replace('.', '', 1).isdigit(): lp = value_clean
                    elif any(c.isalpha() for c in value_clean) and not nazwa: nazwa = value_clean
                    else:
                        try:
                            cleaned = value_clean.replace('zł', '').replace('pln', '').replace(' ', '').replace(',', '.')
                            num_val = float(cleaned)
                            if cena_netto is None: cena_netto = num_val
                            elif cena_brutto is None: cena_brutto = num_val
                        except (ValueError, TypeError): pass
            
            if not nazwa:
                for value in row:
                    if value and any(c.isalpha() for c in value):
                        nazwa = value
                        break
            if not nazwa: nazwa = f"Produkt {lp}"
            
            if cena_netto is not None and cena_brutto is None: cena_brutto = cena_netto * 1.23
            elif cena_brutto is not None and cena_netto is None: cena_netto = cena_brutto / 1.23
            elif cena_netto is None and cena_brutto is None:
                for value in row:
                    try:
                        cleaned = value.replace('zł', '').replace('pln', '').replace(' ', '').replace(',', '.')
                        num_val = float(cleaned)
                        cena_brutto = num_val
                        cena_netto = num_val / 1.23
                        break
                    except (ValueError, TypeError): continue
            
            if cena_netto is None or cena_brutto is None: continue
            
            produkty.append({
                'lp': lp,
                'nazwa': nazwa[:100],
                'cena_netto': round(cena_netto, 2),
                'cena_brutto': round(cena_brutto, 2)
            })
        return produkty, None
    except Exception as e:
        return None, f"Błąd przetwarzania pliku: {str(e)}"

def oblicz_marze_dla_produktu(cena_zakupu, cena_sprzedazy, kategoria, czy_smart=True, koszt_pakowania=0):
    koszt_pakowania = zamien_przecinek_na_kropke(koszt_pakowania) if koszt_pakowania else 0
    if kategoria == "A": prowizja = max(cena_sprzedazy * 0.0615, 0.49)
    elif kategoria in ["B", "C"]: prowizja = max(cena_sprzedazy * 0.1292, 0.49)
    elif kategoria == "D": prowizja = max(cena_sprzedazy * 0.1353, 0.49)
    elif kategoria == "E": prowizja = max(cena_sprzedazy * 0.0555, 0.49)
    elif kategoria == "F": prowizja = max(cena_sprzedazy * 0.1845, 0.49) if cena_sprzedazy <= 60 else max(11.07 + (cena_sprzedazy - 60) * 0.0984, 0.49)
    elif kategoria == "G": prowizja = max(cena_sprzedazy * 0.01, 0.49)
    else: prowizja = max(cena_sprzedazy * 0.1, 0.49)
    
    if czy_smart and kategoria != "G":
        if cena_sprzedazy < 30: dostawa_min = dostawa_max = 0
        elif 30 <= cena_sprzedazy < 45: dostawa_min, dostawa_max = 0.99, 1.99
        elif 45 <= cena_sprzedazy < 65: dostawa_min, dostawa_max = 1.99, 3.99
        elif 65 <= cena_sprzedazy < 100: dostawa_min, dostawa_max = 3.69, 6.09
        elif 100 <= cena_sprzedazy < 150: dostawa_min, dostawa_max = 6.19, 9.49
        else: dostawa_min, dostawa_max = 7.99, 11.89
        
        marza_max = cena_sprzedazy - cena_zakupu - prowizja - dostawa_min - koszt_pakowania
        marza_min = cena_sprzedazy - cena_zakupu - prowizja - dostawa_max - koszt_pakowania
        return {
            'prowizja': prowizja, 'dostawa_min': dostawa_min, 'dostawa_max': dostawa_max,
            'marza_min': marza_min, 'marza_max': marza_max, 'marza_najgorsza': marza_min,
            'marza_procent_min': (marza_min / cena_zakupu * 100) if cena_zakupu > 0 else 0,
            'marza_procent_max': (marza_max / cena_zakupu * 100) if cena_zakupu > 0 else 0,
            'koszt_pakowania': koszt_pakowania
        }
    else:
        marza = cena_sprzedazy - cena_zakupu - prowizja - koszt_pakowania
        return {
            'prowizja': prowizja, 'dostawa_min': 0, 'dostawa_max': 0,
            'marza_min': marza, 'marza_max': marza, 'marza_najgorsza': marza,
            'marza_procent_min': (marza / cena_zakupu * 100) if cena_zakupu > 0 else 0,
            'marza_procent_max': (marza / cena_zakupu * 100) if cena_zakupu > 0 else 0,
            'koszt_pakowania': koszt_pakowania
        }

def oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=None, kategoria_podstawowa=None):
    if kategoria == "A": prowizja_podstawowa = max(cena_sprzedazy * 0.0615, 0.49)
    elif kategoria in ["B", "C"]: prowizja_podstawowa = max(cena_sprzedazy * 0.1292, 0.49)
    elif kategoria == "D": prowizja_podstawowa = max(cena_sprzedazy * 0.1353, 0.49)
    elif kategoria == "E": prowizja_podstawowa = max(cena_sprzedazy * 0.0555, 0.49)
    elif kategoria == "F": prowizja_podstawowa = max(cena_sprzedazy * 0.1845, 0.49) if cena_sprzedazy <= 60 else max(11.07 + (cena_sprzedazy - 60) * 0.0984, 0.49)
    elif kategoria == "G": prowizja_podstawowa = max(cena_sprzedazy * 0.01, 0.49)
    elif kategoria == "H": prowizja_podstawowa = max(cena_sprzedazy * (inna_prowizja / 100), 0.49) if inna_prowizja is not None else 0.49
    elif kategoria == "I":
        if kategoria_podstawowa == "A": prowizja_bazowa = max(cena_sprzedazy * 0.0615, 0.49)
        elif kategoria_podstawowa in ["B", "C"]: prowizja_bazowa = max(cena_sprzedazy * 0.1292, 0.49)
        elif kategoria_podstawowa == "D": prowizja_bazowa = max(cena_sprzedazy * 0.1353, 0.49)
        elif kategoria_podstawowa == "E": prowizja_bazowa = max(cena_sprzedazy * 0.0555, 0.49)
        elif kategoria_podstawowa == "F": prowizja_bazowa = max(cena_sprzedazy * 0.1845, 0.49) if cena_sprzedazy <= 60 else max(11.07 + (cena_sprzedazy - 60) * 0.0984, 0.49)
        elif kategoria_podstawowa == "H": prowizja_bazowa = max(cena_sprzedazy * (inna_prowizja / 100), 0.49) if inna_prowizja is not None else 0.49
        else: prowizja_bazowa = 0.49
        prowizja_podstawowa = max(prowizja_bazowa * 1.6, 0.49)
    else: prowizja_podstawowa = max(cena_sprzedazy * 0.1, 0.49)

    if promowanie and kategoria not in ["G", "I"]: return prowizja_podstawowa, max(prowizja_podstawowa * 1.75, 0.49)
    else: return prowizja_podstawowa, prowizja_podstawowa

def oblicz_koszt_wysylki(cena_sprzedazy):
    return (cena_sprzedazy / 300) * 19.90 if cena_sprzedazy < 300 else 19.90

def oblicz_dostawe_minimalna(cena_sprzedazy):
    if 30 <= cena_sprzedazy < 45: return 1.99
    elif 45 <= cena_sprzedazy < 65: return 3.99
    elif 65 <= cena_sprzedazy < 100: return 6.09
    elif 100 <= cena_sprzedazy < 150: return 9.49
    elif cena_sprzedazy >= 150: return 11.89
    return 0

def oblicz_dostawe_maksymalna(cena_sprzedazy):
    if cena_sprzedazy < 100: return cena_sprzedazy * 0.0949
    elif 100 <= cena_sprzedazy < 150: return 9.49
    else: return 11.89

def oblicz_koszt_dostawy_dla_przewoznika(cena_sprzedazy):
    if cena_sprzedazy < 30:
        return {'Allegro Paczkomaty InPost': 0, 'Allegro Automat Pocztex': 0, 'Allegro One Punkt, Orlen Punkt, DHL BOX': 0, 'Allegro Kurier UPS': 0, 'Allegro Kurier DHL (Allegro Delivery)': 0, 'Allegro Kurier Pocztex': 0, 'Allegro One Kurier (Allegro Delivery)': 0}
    if 30 <= cena_sprzedazy < 45: return {'Allegro Paczkomaty InPost': 1.59, 'Allegro Automat Pocztex': 1.59, 'Allegro One Punkt, Orlen Punkt, DHL BOX': 0.99, 'Allegro Kurier UPS': 1.99, 'Allegro Kurier DHL (Allegro Delivery)': 1.79, 'Allegro Kurier Pocztex': 1.99, 'Allegro One Kurier (Allegro Delivery)': 1.79}
    elif 45 <= cena_sprzedazy < 65: return {'Allegro Paczkomaty InPost': 3.19, 'Allegro Automat Pocztex': 3.19, 'Allegro One Punkt, Orlen Punkt, DHL BOX': 1.99, 'Allegro Kurier UPS': 3.99, 'Allegro Kurier DHL (Allegro Delivery)': 3.69, 'Allegro Kurier Pocztex': 3.99, 'Allegro One Kurier (Allegro Delivery)': 3.69}
    elif 65 <= cena_sprzedazy < 100: return {'Allegro Paczkomaty InPost': 5.19, 'Allegro Automat Pocztex': 5.19, 'Allegro One Punkt, Orlen Punkt, DHL BOX': 3.69, 'Allegro Kurier UPS': 6.09, 'Allegro Kurier DHL (Allegro Delivery)': 5.59, 'Allegro Kurier Pocztex': 6.09, 'Allegro One Kurier (Allegro Delivery)': 5.59}
    elif 100 <= cena_sprzedazy < 150: return {'Allegro Paczkomaty InPost': 7.89, 'Allegro Automat Pocztex': 7.89, 'Allegro One Punkt, Orlen Punkt, DHL BOX': 5.89, 'Allegro Kurier UPS': 9.49, 'Allegro Kurier DHL (Allegro Delivery)': 8.99, 'Allegro Kurier Pocztex': 9.49, 'Allegro One Kurier (Allegro Delivery)': 8.99}
    else: return {'Allegro Paczkomaty InPost': 9.99, 'Allegro Automat Pocztex': 9.99, 'Allegro One Punkt, Orlen Punkt, DHL BOX': 7.99, 'Allegro Kurier UPS': 11.89, 'Allegro Kurier DHL (Allegro Delivery)': 11.29, 'Allegro Kurier Pocztex': 11.89, 'Allegro One Kurier (Allegro Delivery)': 11.29}

def oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_procent=None, marza_kwota=None, promowanie=False, inna_prowizja=None, kategoria_podstawowa=None):
    sugerowana_cena = cena_zakupu
    if marza_kwota: sugerowana_cena += marza_kwota
    elif marza_procent: sugerowana_cena /= (1 - marza_procent / 100)

    for _ in range(10):
        _, prowizja_max = oblicz_prowizje(kategoria, sugerowana_cena, promowanie, inna_prowizja, kategoria_podstawowa)
        dostawa_maksymalna = oblicz_dostawe_maksymalna(sugerowana_cena)
        opłaty_max = prowizja_max + dostawa_maksymalna
        
        if marza_kwota: nowa_sugerowana_cena = cena_zakupu + opłaty_max + marza_kwota
        elif marza_procent: nowa_sugerowana_cena = (cena_zakupu + opłaty_max) / (1 - marza_procent / 100)
        else: nowa_sugerowana_cena = cena_zakupu + opłaty_max

        if abs(nowa_sugerowana_cena - sugerowana_cena) < 0.01: break
        sugerowana_cena = nowa_sugerowana_cena
    return sugerowana_cena, opłaty_max

@app.route("/", methods=["GET", "POST"])
def index():
    if 'dark_mode' not in session: session['dark_mode'] = False
        
    form_marza = KalkulatorMarzyForm()
    form_zakup = KalkulatorZakupuForm()
    form_vat = KalkulatorVATForm()

    if not form_marza.czy_smart.data and request.method == 'GET': form_marza.czy_smart.data = True
    if not form_zakup.czy_smart_zakup.data and request.method == 'GET': form_zakup.czy_smart_zakup.data = True

    if 'historia_marz' not in session: session['historia_marz'] = []

    for wpis in session['historia_marz']:
        if 'koszt_pakowania' not in wpis: wpis['koszt_pakowania'] = 0
        if 'mnoznik_zakupu' not in wpis: wpis['mnoznik_zakupu'] = 1
        if 'mnoznik_sprzedazy' not in wpis: wpis['mnoznik_sprzedazy'] = 1

    # KALKULATOR MARŻY (Standardowy)
    if form_marza.submit.data and form_marza.validate():
        cena_zakupu_wpis = zamien_przecinek_na_kropke(form_marza.cena_zakupu.data)
        mnoznik_zakupu = zamien_przecinek_na_kropke(form_marza.mnoznik_zakupu.data)
        cena_sprzedazy_wpis = zamien_przecinek_na_kropke(form_marza.cena_sprzedazy.data)
        mnoznik_sprzedazy = zamien_przecinek_na_kropke(form_marza.mnoznik_sprzedazy.data)
        
        cena_zakupu = cena_zakupu_wpis * (mnoznik_zakupu if mnoznik_zakupu else 1)
        cena_sprzedazy = cena_sprzedazy_wpis * (mnoznik_sprzedazy if mnoznik_sprzedazy else 1)

        kategoria = form_marza.kategoria.data
        inna_prowizja = form_marza.inna_prowizja.data
        kategoria_podstawowa = form_marza.kategoria_podstawowa.data if kategoria == "I" else None
        ilosc_w_zestawie = zamien_przecinek_na_kropke(form_marza.ilosc_w_zestawie.data)
        czy_smart = form_marza.czy_smart.data
        kwota_dostawy_smart = zamien_przecinek_na_kropke(form_marza.kwota_dostawy_smart.data) if form_marza.kwota_dostawy_smart.data else 0
        koszt_pakowania = zamien_przecinek_na_kropke(form_marza.koszt_pakowania.data) if form_marza.koszt_pakowania.data else 0
        marza_kwota = zamien_przecinek_na_kropke(form_marza.marza_kwota.data) if form_marza.marza_kwota.data else 2
        marza_procent = zamien_przecinek_na_kropke(form_marza.marza_procent.data) if form_marza.marza_procent.data else 15

        cena_zakupu_total = cena_zakupu * ilosc_w_zestawie
        cena_sprzedazy_total = cena_sprzedazy * ilosc_w_zestawie

        if kategoria == "H" and inna_prowizja: inna_prowizja = zamien_przecinek_na_kropke(inna_prowizja)

        if not czy_smart and kategoria not in ["G", "I"]:
            cena_sprzedazy_z_dostawa = cena_sprzedazy_total + kwota_dostawy_smart
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_z_dostawa, promowanie=False, inna_prowizja=inna_prowizja if kategoria == "H" else None)
            
            marza_min = cena_sprzedazy_total - cena_zakupu_total - prowizja_min - kwota_dostawy_smart - koszt_pakowania
            marza_max = cena_sprzedazy_total - cena_zakupu_total - prowizja_max - kwota_dostawy_smart - koszt_pakowania
            
            sugerowana_cena_min, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_kwota=marza_kwota, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
            sugerowana_cena_procent, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_procent=marza_procent, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
            
            wynik_bez_promowania = f"""
            <h3>Bez promowania (tryb nie-smart)</h3>
            <div class="wynik">
                <table>
                    <tr><th>Marża minimalna</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{marza_min:.2f}" style="color:var(--green-color);">{marza_min:.2f} zł</span></td></tr>
                    <tr><th>Marża maksymalna</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{marza_max:.2f}" style="color:var(--green-color);">{marza_max:.2f} zł</span></td></tr>
                    <tr><th>Prowizja</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{prowizja_min:.2f}" style="color:var(--red-color);">{prowizja_min:.2f} zł</span></td></tr>
                    <tr><th>Min sugerowana cena (marża {marza_kwota:.2f} zł)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{sugerowana_cena_min:.2f}" style="color:var(--blue-color);">{sugerowana_cena_min:.2f} zł</span></td></tr>
                    <tr><th>Sugerowana cena (marża {marza_procent:.1f}%)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{sugerowana_cena_procent:.2f}" style="color:var(--blue-color);">{sugerowana_cena_procent:.2f} zł</span></td></tr>
                </table>
            </div>
            """
            session['wynik_marza'] = wynik_bez_promowania
        else:
            if kategoria == "G":
                prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=False)
                koszt_wysylki = oblicz_koszt_wysylki(cena_sprzedazy_total)
                marza_darmowa_wysylka = cena_sprzedazy_total - cena_zakupu_total - (prowizja_max + koszt_wysylki) - koszt_pakowania
                marza_maksymalna = cena_sprzedazy_total - cena_zakupu_total - prowizja_max - koszt_pakowania
                sugerowana_cena = cena_zakupu_total / 0.84

                wynik_html = f"""
                <h3>Wyniki dla kategorii G (Sklep internetowy)</h3>
                <div class="wynik">
                    <table>
                        <tr><th>Prowizja (bez dostawy)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{prowizja_max:.2f}" style="color:var(--red-color);">{prowizja_max:.2f} zł</span></td></tr>
                        <tr><th>Prowizja z darmową wysyłką</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{prowizja_max + koszt_wysylki:.2f}" style="color:var(--red-color);">{(prowizja_max + koszt_wysylki):.2f} zł</span></td></tr>
                        <tr><th>Marża przy darmowej wysyłce</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{marza_darmowa_wysylka:.2f}" style="color:var(--green-color);">{marza_darmowa_wysylka:.2f} zł</span></td></tr>
                        <tr><th>Marża maksymalna</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{marza_maksymalna:.2f}" style="color:var(--green-color);">{marza_maksymalna:.2f} zł</span></td></tr>
                        <tr><th>Sugerowana cena sprzedaży</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{sugerowana_cena:.2f}" style="color:var(--blue-color);">{sugerowana_cena:.2f} zł</span></td></tr>
                    </table>
                </div>
                """
                session['wynik_marza'] = wynik_html
            else:
                prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=False, inna_prowizja=inna_prowizja if kategoria == "H" else None, kategoria_podstawowa=kategoria_podstawowa if kategoria == "I" else None)
                dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy_total)
                dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy_total)

                sugerowana_cena_min, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_kwota=marza_kwota, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
                sugerowana_cena_procent, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_procent=marza_procent, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)

                koszty_dostaw = oblicz_koszt_dostawy_dla_przewoznika(cena_sprzedazy_total)
                marze_przewoznicy = [cena_sprzedazy_total - cena_zakupu_total - prowizja_min - k - koszt_pakowania for k in koszty_dostaw.values()]
                marza_min_przewoznicy = min(marze_przewoznicy)
                marza_max_przewoznicy = max(marze_przewoznicy)
                marza_najgorsza_opcja = cena_sprzedazy_total - cena_zakupu_total - prowizja_max - dostawa_maksymalna - koszt_pakowania

                wynik_bez_promowania = f"""
                <h3>Bez promowania</h3>
                <div class="wynik">
                    <table>
                        <tr><th>Marża (przedział dla przewoźników)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{marza_min_przewoznicy:.2f} - {marza_max_przewoznicy:.2f}" style="color:var(--green-color);">{marza_min_przewoznicy:.2f} - {marza_max_przewoznicy:.2f} zł</span><button class="toggle-tabela" onclick="toggleTabela('tabela-przewoznicy-bez-promowania')" style="margin-left: 10px; padding: 2px 8px; font-size: 12px;">pokaż szczegóły</button></td></tr>
                        <tr><th>Marża w najgorszej opcji</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{marza_najgorsza_opcja:.2f}" style="color:var(--orange-color);">{marza_najgorsza_opcja:.2f} zł</span></td></tr>
                        <tr><th>Prowizja czysta (bez dostawy)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{prowizja_min:.2f}" style="color:var(--red-color);">{prowizja_min:.2f} zł</span></td></tr>
                        <tr><th>Prowizja z dostawą minimalną</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{prowizja_min + dostawa_minimalna:.2f}" style="color:var(--red-color);">{(prowizja_min + dostawa_minimalna):.2f} zł</span></td></tr>
                        <tr><th>Prowizja z dostawą maksymalną</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{prowizja_max + dostawa_maksymalna:.2f}" style="color:var(--red-color);">{(prowizja_max + dostawa_maksymalna):.2f} zł</span></td></tr>
                        <tr><th>Min sugerowana cena (marża {marza_kwota:.2f} zł)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{sugerowana_cena_min:.2f}" style="color:var(--blue-color);">{sugerowana_cena_min:.2f} zł</span></td></tr>
                        <tr><th>Sugerowana cena (marża {marza_procent:.1f}%)</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{sugerowana_cena_procent:.2f}" style="color:var(--blue-color);">{sugerowana_cena_procent:.2f} zł</span></td></tr>
                    </table>
                </div>
                """
                
                tabela_przewoznikow = "".join([f'<tr><td>{p}</td><td>{k:.2f} zł</td><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_sprzedazy_total - cena_zakupu_total - prowizja_min - k - koszt_pakowania:.2f}" style="color:var(--green-color);">{(cena_sprzedazy_total - cena_zakupu_total - prowizja_min - k - koszt_pakowania):.2f} zł</span></td></tr>' for p, k in koszty_dostaw.items()])
                
                wynik_przewoznicy = f"""
                <div id="tabela-przewoznicy-bez-promowania" class="rozwijana-tabela" style="display: none;">
                    <h4>Szczegóły marż dla przewoźników (bez promowania)</h4>
                    <div class="wynik"><table><thead><tr><th>Przewoźnik</th><th>Koszt dostawy</th><th>Marża</th></tr></thead><tbody>{tabela_przewoznikow}</tbody></table></div>
                </div>
                """
                session['wynik_marza'] = f"{wynik_bez_promowania}{wynik_przewoznicy}"

        historia_wpis = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cena_zakupu': zamien_przecinek_na_kropke(form_marza.cena_zakupu.data),
            'mnoznik_zakupu': mnoznik_zakupu if mnoznik_zakupu else 1.0,
            'cena_sprzedazy': zamien_przecinek_na_kropke(form_marza.cena_sprzedazy.data),
            'mnoznik_sprzedazy': mnoznik_sprzedazy if mnoznik_sprzedazy else 1.0,
            'kategoria': kategoria,
            'marza_kwota': marza_kwota,
            'marza_procent': marza_procent,
            'czy_smart': czy_smart,
            'koszt_pakowania': koszt_pakowania
        }
        session['historia_marz'].insert(0, historia_wpis)
        session['historia_marz'] = session['historia_marz'][:10]
        session.modified = True

    # KALKULATOR ZAKUPU (Odwrócony)
    if form_zakup.submit_zakup.data and form_zakup.validate():
        cena_sprz = zamien_przecinek_na_kropke(form_zakup.cena_sprzedazy_docelowa.data)
        marza_doc = zamien_przecinek_na_kropke(form_zakup.oczekiwana_marza.data)
        kat = form_zakup.kategoria_zakup.data
        inna_prow = form_zakup.inna_prowizja_zakup.data
        kat_podst = form_zakup.kategoria_podstawowa_zakup.data if kat == "I" else None
        czy_smart_zakup = form_zakup.czy_smart_zakup.data
        kwota_dost_ns = zamien_przecinek_na_kropke(form_zakup.kwota_dostawy_smart_zakup.data) if form_zakup.kwota_dostawy_smart_zakup.data else 0
        koszt_pak = zamien_przecinek_na_kropke(form_zakup.koszt_pakowania_zakup.data) if form_zakup.koszt_pakowania_zakup.data else 0
        
        if kat == "H" and inna_prow:
            inna_prow = zamien_przecinek_na_kropke(inna_prow)

        if not czy_smart_zakup and kat not in ["G", "I"]:
            cena_sprzedazy_z_dostawa = cena_sprz + kwota_dost_ns
            prowizja_min, _ = oblicz_prowizje(kat, cena_sprzedazy_z_dostawa, promowanie=False, inna_prowizja=inna_prow if kat == "H" else None)
            cena_zakupu_wymagana = cena_sprz - prowizja_min - kwota_dost_ns - koszt_pak - marza_doc
            
            wynik_zakup_html = f"""
            <h3>Wynik kalkulacji (tryb nie-smart)</h3>
            <div class="wynik">
                <table>
                    <tr>
                        <th>Maksymalna cena zakupu</th>
                        <td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_zakupu_wymagana:.2f}" style="color:var(--green-color); font-weight:bold;">{cena_zakupu_wymagana:.2f} zł</span></td>
                    </tr>
                </table>
            </div>
            """
            session['wynik_zakup'] = wynik_zakup_html
        elif kat == "G":
            prowizja_min, prowizja_max = oblicz_prowizje(kat, cena_sprz, promowanie=False)
            koszt_wys = oblicz_koszt_wysylki(cena_sprz)
            cena_zakupu_darmowa_wys = cena_sprz - prowizja_max - koszt_wys - koszt_pak - marza_doc
            cena_zakupu_bez_wys = cena_sprz - prowizja_max - koszt_pak - marza_doc
            
            wynik_zakup_html = f"""
            <h3>Wynik kalkulacji (Sklep internetowy)</h3>
            <div class="wynik">
                <table>
                    <tr>
                        <th>Maksymalna cena zakupu (z darmową wysyłką)</th>
                        <td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_zakupu_darmowa_wys:.2f}" style="color:var(--orange-color); font-weight:bold;">{cena_zakupu_darmowa_wys:.2f} zł</span></td>
                    </tr>
                    <tr>
                        <th>Maksymalna cena zakupu (bez wysyłki)</th>
                        <td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_zakupu_bez_wys:.2f}" style="color:var(--green-color); font-weight:bold;">{cena_zakupu_bez_wys:.2f} zł</span></td>
                    </tr>
                </table>
            </div>
            """
            session['wynik_zakup'] = wynik_zakup_html
        else:
            prowizja_min, prowizja_max = oblicz_prowizje(kat, cena_sprz, promowanie=False, inna_prowizja=inna_prow if kat == "H" else None, kategoria_podstawowa=kat_podst if kat == "I" else None)
            dostawa_max = oblicz_dostawe_maksymalna(cena_sprz)
            koszty_dostaw = oblicz_koszt_dostawy_dla_przewoznika(cena_sprz)
            
            cena_zakupu_najgorsza = cena_sprz - prowizja_min - dostawa_max - koszt_pak - marza_doc
            
            ceny_z_przew = []
            for przewoznik, koszt in koszty_dostaw.items():
                cena_z = cena_sprz - prowizja_min - koszt - koszt_pak - marza_doc
                ceny_z_przew.append((przewoznik, koszt, cena_z))
            
            min_cena_z = min(c[2] for c in ceny_z_przew)
            max_cena_z = max(c[2] for c in ceny_z_przew)
            
            tabela_zakup_przewoznikow = "".join([f'<tr><td>{p}</td><td>{k:.2f} zł</td><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{c:.2f}" style="color:var(--green-color);">{c:.2f} zł</span></td></tr>' for p, k, c in ceny_z_przew])
            
            wynik_zakup_html = f"""
            <h3>Wynik kalkulacji zakupu</h3>
            <div class="wynik">
                <table>
                    <tr>
                        <th>Maks. cena zakupu (najgorsza opcja)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{cena_zakupu_najgorsza:.2f}" style="color:var(--orange-color); font-weight:bold;">
                                {cena_zakupu_najgorsza:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Maks. cena zakupu (przedział dla przewoźników)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{min_cena_z:.2f} - {max_cena_z:.2f}" style="color:var(--green-color); font-weight:bold;">
                                {min_cena_z:.2f} - {max_cena_z:.2f} zł
                            </span>
                            <button class="toggle-tabela" onclick="toggleTabela('tabela-zakup-przewoznicy')" style="margin-left: 10px; padding: 2px 8px; font-size: 12px;">pokaż szczegóły</button>
                        </td>
                    </tr>
                </table>
            </div>
            <div id="tabela-zakup-przewoznicy" class="rozwijana-tabela" style="display: none;">
                <h4>Szczegóły dla przewoźników (cena zakupu)</h4>
                <div class="wynik"><table><thead><tr><th>Przewoźnik</th><th>Koszt dostawy</th><th>Wymagana cena zakupu</th></tr></thead><tbody>{tabela_zakup_przewoznikow}</tbody></table></div>
            </div>
            """
            session['wynik_zakup'] = wynik_zakup_html

    # KALKULATOR VAT
    if form_vat.submit.data and form_vat.validate():
        cena_netto = zamien_przecinek_na_kropke(form_vat.cena_netto.data)
        vat = zamien_przecinek_na_kropke(form_vat.vat.data)
        ilosc_sztuk = form_vat.ilosc_sztuk.data
        koszt_dostawy_sztuka = zamien_przecinek_na_kropke(form_vat.koszt_dostawy_sztuka.data)
        kwota_dostawy = zamien_przecinek_na_kropke(form_vat.kwota_dostawy.data)
        ilosc_w_dostawie = form_vat.ilosc_w_dostawie.data
        
        kurs_info_towar = ""
        kurs_error_towar = ""
        if form_vat.inna_waluta_towar.data:
            if form_vat.typ_kursu_towar.data == 'wlasny':
                kurs_waluty_towar = zamien_przecinek_na_kropke(form_vat.kurs_waluty_towar.data) if form_vat.kurs_waluty_towar.data else 1.0
                kurs_info_towar = f"Użyto własnego kursu: 1 {form_vat.waluta_towar.data} = {kurs_waluty_towar:.4f} PLN"
            else:
                data_kursu = form_vat.data_kursu_towar.data if form_vat.typ_kursu_towar.data == 'historyczny' else None
                kurs_waluty_towar = pobierz_kurs_waluty(form_vat.waluta_towar.data, data_kursu)
                if kurs_waluty_towar is None:
                    kurs_error_towar = f"Nie udało się pobrać kursu {form_vat.waluta_towar.data}!"
                    kurs_waluty_towar = 1.0
                else:
                    if form_vat.typ_kursu_towar.data == 'historyczny': kurs_info_towar = f"Kurs {form_vat.waluta_towar.data} z dnia {form_vat.data_kursu_towar.data}: 1 {form_vat.waluta_towar.data} = {kurs_waluty_towar:.4f} PLN"
                    else: kurs_info_towar = f"Aktualny kurs {form_vat.waluta_towar.data}: 1 {form_vat.waluta_towar.data} = {kurs_waluty_towar:.4f} PLN"
            cena_netto *= kurs_waluty_towar
        
        kurs_info_dostawa = ""
        kurs_error_dostawa = ""
        if form_vat.inna_waluta_dostawa.data:
            if form_vat.typ_kursu_dostawa.data == 'wlasny':
                kurs_waluty_dostawa = zamien_przecinek_na_kropke(form_vat.kurs_waluty_dostawa.data) if form_vat.kurs_waluty_dostawa.data else 1.0
                kurs_info_dostawa = f"Użyto własnego kursu: 1 {form_vat.waluta_dostawa.data} = {kurs_waluty_dostawa:.4f} PLN"
            else:
                data_kursu = form_vat.data_kursu_dostawa.data if form_vat.typ_kursu_dostawa.data == 'historyczny' else None
                kurs_waluty_dostawa = pobierz_kurs_waluty(form_vat.waluta_dostawa.data, data_kursu)
                if kurs_waluty_dostawa is None:
                    kurs_error_dostawa = f"Nie udało się pobrać kursu {form_vat.waluta_dostawa.data}!"
                    kurs_waluty_dostawa = 1.0
                else:
                    if form_vat.typ_kursu_dostawa.data == 'historyczny': kurs_info_dostawa = f"Kurs {form_vat.waluta_dostawa.data} z dnia {form_vat.data_kursu_dostawa.data}: 1 {form_vat.waluta_dostawa.data} = {kurs_waluty_dostawa:.4f} PLN"
                    else: kurs_info_dostawa = f"Aktualny kurs {form_vat.waluta_dostawa.data}: 1 {form_vat.waluta_dostawa.data} = {kurs_waluty_dostawa:.4f} PLN"
            if kwota_dostawy: kwota_dostawy *= kurs_waluty_dostawa
            else: koszt_dostawy_sztuka *= kurs_waluty_dostawa

        cena_netto_za_sztuke = cena_netto / ilosc_sztuk
        if kwota_dostawy and ilosc_w_dostawie: koszt_dostawy_sztuka = kwota_dostawy / ilosc_w_dostawie
        cena_brutto_za_sztuke = cena_netto_za_sztuke * (1 + vat / 100)
        cena_brutto_z_dostawa_za_sztuke = cena_brutto_za_sztuke + koszt_dostawy_sztuka

        kurs_info_html = ""
        if form_vat.inna_waluta_towar.data or form_vat.inna_waluta_dostawa.data:
            kurs_info_html = "<div style='margin-bottom: 20px;'>"
            if form_vat.inna_waluta_towar.data:
                if kurs_error_towar: kurs_info_html += f"<p style='color:var(--red-color);'><strong>Błąd towaru:</strong> {kurs_error_towar}</p>"
                else: kurs_info_html += f"<p><strong>Towar:</strong> {kurs_info_towar}</p>"
            if form_vat.inna_waluta_dostawa.data:
                if kurs_error_dostawa: kurs_info_html += f"<p style='color:var(--red-color);'><strong>Błąd dostawy:</strong> {kurs_error_dostawa}</p>"
                else: kurs_info_html += f"<p><strong>Dostawa:</strong> {kurs_info_dostawa}</p>"
            kurs_info_html += "</div>"

        session['wynik_vat'] = f"""
        <h3>Wyniki kalkulatora VAT</h3>
        {kurs_info_html}
        <div class="wynik">
            <table>
                <tr><th>Cena brutto za sztukę:</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_brutto_za_sztuke:.2f}" style="color:var(--blue-color);">{cena_brutto_za_sztuke:.2f} zł</span></td></tr>
                <tr><th>Cena brutto z dostawą za sztukę:</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_brutto_z_dostawa_za_sztuke:.2f}" style="color:var(--blue-color);">{cena_brutto_z_dostawa_za_sztuke:.2f} zł</span></td></tr>
                <tr><th>Cena netto za sztukę:</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_netto_za_sztuke:.2f}" style="color:var(--blue-color);">{cena_netto_za_sztuke:.2f} zł</span></td></tr>
                <tr><th>Koszt dostawy na sztukę:</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{koszt_dostawy_sztuka:.2f}" style="color:var(--blue-color);">{koszt_dostawy_sztuka:.2f} zł</span></td></tr>
                <tr><th>Cena brutto całkowita:</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_brutto_za_sztuke * ilosc_sztuk:.2f}" style="color:var(--blue-color);">{(cena_brutto_za_sztuke * ilosc_sztuk):.2f} zł</span></td></tr>
                <tr><th>Cena brutto z dostawą całkowita:</th><td><span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" data-value="{cena_brutto_z_dostawa_za_sztuke * ilosc_sztuk:.2f}" style="color:var(--blue-color);">{(cena_brutto_z_dostawa_za_sztuke * ilosc_sztuk):.2f} zł</span></td></tr>
            </table>
        </div>
        """

    return render_template(
        "index.html",
        form_marza=form_marza,
        form_zakup=form_zakup,
        form_vat=form_vat,
        wynik_marza=session.get('wynik_marza'),
        wynik_zakup=session.get('wynik_zakup'),
        wynik_vat=session.get('wynik_vat'),
        historia_marz=session.get('historia_marz', [])
    )

@app.route("/licznik", methods=["GET", "POST"])
def licznik():
    if 'dark_mode' not in session: session['dark_mode'] = False
    text = ""
    znaki = slowa = linie = 0
    
    if request.method == "POST":
        text = request.form.get("tekst", "")
        znaki = len(text)
        slowa = len(text.split()) if text else 0
        linie = len(text.splitlines()) if text else 0
    return render_template("licznik.html", text=text, znaki=znaki, slowa=slowa, linie=linie)

@app.route("/porownaj", methods=["GET", "POST"])
def porownaj():
    if 'dark_mode' not in session: session['dark_mode'] = False
    tekst1 = tekst2 = roznice = ""
    statystyki1 = {"znaki": 0, "slowa": 0, "linie": 0}
    statystyki2 = {"znaki": 0, "slowa": 0, "linie": 0}
    podobienstwo = 0.0
    
    if request.method == "POST":
        tekst1 = request.form.get("tekst1", "")
        tekst2 = request.form.get("tekst2", "")
        statystyki1 = {"znaki": len(tekst1), "slowa": len(tekst1.split()) if tekst1 else 0, "linie": len(tekst1.splitlines()) if tekst1 else 0}
        statystyki2 = {"znaki": len(tekst2), "slowa": len(tekst2.split()) if tekst2 else 0, "linie": len(tekst2.splitlines()) if tekst2 else 0}
        
        if tekst1 and tekst2:
            podobienstwo = difflib.SequenceMatcher(None, tekst1, tekst2).ratio() * 100
            roznice = "\n".join(list(difflib.Differ().compare(tekst1.splitlines(), tekst2.splitlines())))
        elif tekst1 or tekst2:
            podobienstwo = 0.0
            roznice = ""

    return render_template("porownaj.html", tekst1=tekst1, tekst2=tekst2, roznice=roznice, statystyki1=statystyki1, statystyki2=statystyki2, podobienstwo=podobienstwo)

@app.route("/zbiorczy", methods=["GET", "POST"])
def zbiorczy():
    if 'dark_mode' not in session: session['dark_mode'] = False
        
    wyniki_zbiorcze = error_message = None
    laczna_marza_min = laczna_marza_max = laczna_marza_najgorsza = laczna_cena_zakupu = laczna_cena_sprzedazy = liczba_produktow = 0
    
    if request.method == "POST" and (request.form.get('form_type') == 'zbiorczy' or 'submit_zbiorczy' in request.form):
        plik_csv = request.files.get('plik_csv')
        kategoria = request.form.get('kategoria_zbiorcza', 'A')
        czy_smart = 'czy_smart_zbiorcze' in request.form
        try: koszt_pakowania = zamien_przecinek_na_kropke(request.form.get('koszt_pakowania_zbiorcze', '0'))
        except: koszt_pakowania = 0
        
        if plik_csv and plik_csv.filename and plik_csv.filename.endswith(('.csv', '.txt')):
            produkty, error = przetworz_dane_zbiorcze(plik_csv, kategoria, czy_smart, koszt_pakowania)
            
            if error: error_message = error
            elif produkty:
                wyniki = []
                for produkt in produkty:
                    cena_zakupu = produkt['cena_netto']
                    cena_sprzedazy = produkt['cena_brutto']
                    marza_dane = oblicz_marze_dla_produktu(cena_zakupu, cena_sprzedazy, kategoria, czy_smart, koszt_pakowania)
                    wyniki.append({'lp': produkt['lp'], 'nazwa': produkt['nazwa'], 'cena_zakupu': cena_zakupu, 'cena_sprzedazy': cena_sprzedazy, 'prowizja': marza_dane['prowizja'], 'dostawa_min': marza_dane['dostawa_min'], 'dostawa_max': marza_dane['dostawa_max'], 'marza_min': marza_dane['marza_min'], 'marza_max': marza_dane['marza_max'], 'marza_najgorsza': marza_dane['marza_najgorsza'], 'marza_procent_min': marza_dane['marza_procent_min'], 'marza_procent_max': marza_dane['marza_procent_max'], 'koszt_pakowania': marza_dane['koszt_pakowania']})
                    laczna_marza_min += marza_dane['marza_min']
                    laczna_marza_max += marza_dane['marza_max']
                    laczna_marza_najgorsza += marza_dane['marza_najgorsza']
                    laczna_cena_zakupu += cena_zakupu
                    laczna_cena_sprzedazy += cena_sprzedazy
                    liczba_produktow += 1
                wyniki_zbiorcze = wyniki
            else: error_message = "Nie udało się przetworzyć pliku. Sprawdź format."
        else:
            if not plik_csv or not plik_csv.filename: error_message = "Proszę wybrać plik CSV do przesłania"
            elif not plik_csv.filename.endswith(('.csv', '.txt')): error_message = "Proszę wybrać plik z rozszerzeniem .csv lub .txt"

    return render_template(
        "zbiorczy.html", wyniki_zbiorcze=wyniki_zbiorcze, laczna_marza_min=laczna_marza_min, laczna_marza_max=laczna_marza_max, laczna_marza_najgorsza=laczna_marza_najgorsza, laczna_cena_zakupu=laczna_cena_zakupu, laczna_cena_sprzedazy=laczna_cena_sprzedazy, liczba_produktow=liczba_produktow, error_message=error_message, kategoria_zbiorcza=request.form.get('kategoria_zbiorcza', 'A') if request.method == 'POST' else 'A', czy_smart_zbiorcze='czy_smart_zbiorcze' in request.form if request.method == 'POST' else True, koszt_pakowania_zbiorcze=request.form.get('koszt_pakowania_zbiorcze', '0') if request.method == 'POST' else '0'
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)