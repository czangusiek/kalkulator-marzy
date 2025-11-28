import os
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, BooleanField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import datetime, timedelta
import requests
import difflib
import json
import csv
import io

app = Flask(__name__)
app.secret_key = 'tajny_klucz'
app.config['SESSION_TYPE'] = 'filesystem'

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

class KalkulatorMarzyForm(FlaskForm):
    cena_zakupu = StringField('Cena zakupu:', validators=[DataRequired()])
    cena_sprzedazy = StringField('Cena sprzedaży:', validators=[DataRequired()])
    kategoria = SelectField('Kategoria:', choices=[
        ('A', 'Supermarket (6,15%)'),
        ('B', 'Cukier (12,92%)'),
        ('C', 'Chemia gospodarcza (12,92%)'),
        ('D', 'AGD zwykłe (13,53%)'),
        ('E', 'Elektronika (5,55%)'),
        ('F', 'Chemia do 60 zł (18,45% / 9,84%)'),
        ('G', 'Sklep internetowy'),
        ('H', 'Inna prowizja'),
        ('I', 'Strefa okazji (+60% prowizji podstawowej)')
    ], validators=[DataRequired()])
    inna_prowizja = StringField('Procent prowizji:')
    kategoria_podstawowa = SelectField('Kategoria podstawowa:', choices=[
        ('A', 'Supermarket (6,15%)'),
        ('B', 'Cukier (12,92%)'),
        ('C', 'Chemia gospodarcza (12,92%)'),
        ('D', 'AGD zwykłe (13,53%)'),
        ('E', 'Elektronika (5,55%)'),
        ('F', 'Chemia do 60 zł (18,45% / 9,84%)'),
        ('H', 'Inna prowizja')
    ], validators=[Optional()])
    ilosc_w_zestawie = StringField('Ilość w zestawie:', default="1", validators=[DataRequired()])
    czy_smart = BooleanField('Czy smart?', default=True)
    kwota_dostawy_smart = StringField('Kwota dostawy:', default="0")
    koszt_pakowania = StringField('Koszt pakowania (zł):', default="0")
    marza_kwota = StringField('Marża minimalna (zł):', default="2")
    marza_procent = StringField('Marża procentowa (%):', default="15")
    submit = SubmitField('Oblicz')

class KalkulatorVATForm(FlaskForm):
    cena_netto = StringField('Wpisz cenę netto:', validators=[DataRequired()])
    vat = SelectField('Wybierz podatek VAT:', choices=[
        ('5', '5%'),
        ('8', '8%'),
        ('23', '23%')
    ], default="23", validators=[DataRequired()])
    ilosc_sztuk = IntegerField('Ilość sztuk w cenie netto:', default=1, validators=[NumberRange(min=1)])
    koszt_dostawy_sztuka = StringField('Wpisz koszt dostawy na sztukę:', default="0")
    kwota_dostawy = StringField('Lub wpisz kwotę dostawy:', default="0")
    ilosc_w_dostawie = IntegerField('Ilość sztuk w dostawie:', default=1, validators=[NumberRange(min=1)])
    inna_waluta_towar = BooleanField('Inna waluta niż PLN (towar)', default=False)
    typ_kursu_towar = SelectField('Typ kursu:', choices=[
        ('aktualny', 'Aktualny kurs'),
        ('historyczny', 'Kurs z dnia'),
        ('wlasny', 'Własny kurs')
    ], default='aktualny')
    data_kursu_towar = StringField('Data kursu (RRRR-MM-DD):', default=datetime.now().strftime('%Y-%m-%d'))
    waluta_towar = SelectField('Waluta:', choices=[
        ('USD', 'USD (dolar amerykański)'),
        ('EUR', 'EUR (euro)'),
        ('GBP', 'GBP (funt brytyjski)')
    ], default='USD')
    kurs_waluty_towar = StringField('Kurs waluty (1 waluta = X PLN):', default="1.0", validators=[Optional()])
    inna_waluta_dostawa = BooleanField('Inna waluta niż PLN (dostawa)', default=False)
    typ_kursu_dostawa = SelectField('Typ kursu:', choices=[
        ('aktualny', 'Aktualny kurs'),
        ('historyczny', 'Kurs z dnia'),
        ('wlasny', 'Własny kurs')
    ], default='aktualny')
    data_kursu_dostawa = StringField('Data kursu (RRRR-MM-DD):', default=datetime.now().strftime('%Y-%m-%d'))
    waluta_dostawa = SelectField('Waluta:', choices=[
        ('USD', 'USD (dolar amerykański)'),
        ('EUR', 'EUR (euro)'),
        ('GBP', 'GBP (funt brytyjski)')
    ], default='USD')
    kurs_waluty_dostawa = StringField('Kurs waluty (1 waluta = X PLN):', default="1.0", validators=[Optional()])
    submit = SubmitField('Oblicz')

class KalkulatorZbiorczyForm(FlaskForm):
    plik_csv = StringField('Dane CSV:')
    kategoria_zbiorcza = SelectField('Kategoria:', choices=[
        ('A', 'Supermarket (6,15%)'),
        ('B', 'Cukier (12,92%)'),
        ('C', 'Chemia gospodarcza (12,92%)'),
        ('D', 'AGD zwykłe (13,53%)'),
        ('E', 'Elektronika (5,55%)'),
        ('F', 'Chemia do 60 zł (18,45% / 9,84%)'),
        ('G', 'Sklep internetowy'),
        ('H', 'Inna prowizja'),
        ('I', 'Strefa okazji (+60% prowizji podstawowej)')
    ], default="A", validators=[DataRequired()])
    czy_smart_zbiorcze = BooleanField('Czy smart?', default=True)
    koszt_pakowania_zbiorcze = StringField('Koszt pakowania na sztukę (zł):', default="0")
    submit_zbiorczy = SubmitField('Oblicz marże zbiorczo')

def zamien_przecinek_na_kropke(liczba):
    if isinstance(liczba, str):
        return float(liczba.replace(",", "."))
    return liczba

def przetworz_dane_zbiorcze(dane_csv, kategoria, czy_smart, koszt_pakowania):
    """Przetwarza dane CSV i oblicza marże dla każdego produktu"""
    try:
        # Konwersja danych CSV
        if isinstance(dane_csv, str):
            csv_data = io.StringIO(dane_csv)
        else:
            csv_data = io.StringIO(dane_csv.read().decode('utf-8-sig'))
        
        reader = csv.DictReader(csv_data, delimiter=';')
        if reader.fieldnames is None:
            reader = csv.DictReader(csv_data, delimiter=',')
        
        produkty = []
        for row in reader:
            # Szukamy kolumn z cenami (case insensitive)
            cena_netto = None
            cena_brutto = None
            nazwa = ""
            
            for key, value in row.items():
                key_lower = key.lower().strip()
                if 'nazwa' in key_lower or 'nazwa' in key_lower:
                    nazwa = value.strip()
                elif 'netto' in key_lower:
                    try:
                        cena_netto = zamien_przecinek_na_kropke(value) if value.strip() else None
                    except:
                        cena_netto = None
                elif 'brutto' in key_lower:
                    try:
                        cena_brutto = zamien_przecinek_na_kropke(value) if value.strip() else None
                    except:
                        cena_brutto = None
            
            # Oblicz brakującą cenę
            if cena_netto is not None and cena_brutto is None:
                cena_brutto = cena_netto * 1.23  # domyślnie 23% VAT
            elif cena_brutto is not None and cena_netto is None:
                cena_netto = cena_brutto / 1.23
            
            if cena_netto is not None and cena_brutto is not None and nazwa:
                produkty.append({
                    'nazwa': nazwa,
                    'cena_netto': cena_netto,
                    'cena_brutto': cena_brutto
                })
        
        return produkty
    except Exception as e:
        print(f"Błąd przetwarzania CSV: {e}")
        return []

def oblicz_marze_dla_produktu(cena_zakupu, cena_sprzedazy, kategoria, czy_smart=True, koszt_pakowania=0):
    """Oblicza marżę dla pojedynczego produktu"""
    koszt_pakowania = zamien_przecinek_na_kropke(koszt_pakowania) if koszt_pakowania else 0
    
    if kategoria == "A":
        prowizja = cena_sprzedazy * 0.0615
    elif kategoria == "B":
        prowizja = cena_sprzedazy * 0.1292
    elif kategoria == "C":
        prowizja = cena_sprzedazy * 0.1292
    elif kategoria == "D":
        prowizja = cena_sprzedazy * 0.1353
    elif kategoria == "E":
        prowizja = cena_sprzedazy * 0.0555
    elif kategoria == "F":
        if cena_sprzedazy <= 60:
            prowizja = cena_sprzedazy * 0.1845
        else:
            prowizja = 11.07 + (cena_sprzedazy - 60) * 0.0984
    elif kategoria == "G":
        prowizja = cena_sprzedazy * 0.01
    else:
        prowizja = cena_sprzedazy * 0.1
    
    if czy_smart and kategoria != "G":
        # Dla trybu smart uwzględniamy koszty dostawy
        if cena_sprzedazy < 30:
            dostawa = 0
        elif 30 <= cena_sprzedazy < 45:
            dostawa = 1.99
        elif 45 <= cena_sprzedazy < 65:
            dostawa = 3.99
        elif 65 <= cena_sprzedazy < 100:
            dostawa = 5.79
        elif 100 <= cena_sprzedazy < 150:
            dostawa = 9.09
        else:
            dostawa = 11.49
    else:
        dostawa = 0
    
    marza_netto = cena_sprzedazy - cena_zakupu - prowizja - dostawa - koszt_pakowania
    marza_procent = (marza_netto / cena_zakupu * 100) if cena_zakupu > 0 else 0
    
    return {
        'prowizja': prowizja,
        'dostawa': dostawa,
        'marza_netto': marza_netto,
        'marza_procent': marza_procent,
        'koszt_pakowania': koszt_pakowania
    }

def oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=None, kategoria_podstawowa=None):
    if kategoria == "A":
        prowizja = cena_sprzedazy * 0.0615
    elif kategoria == "B":
        prowizja = cena_sprzedazy * 0.1292
    elif kategoria == "C":
        prowizja = cena_sprzedazy * 0.1292
    elif kategoria == "D":
        prowizja = cena_sprzedazy * 0.1353
    elif kategoria == "E":
        prowizja = cena_sprzedazy * 0.0555
    elif kategoria == "F":
        if cena_sprzedazy <= 60:
            prowizja = cena_sprzedazy * 0.1845
        else:
            prowizja = 11.07 + (cena_sprzedazy - 60) * 0.0984
    elif kategoria == "G":
        prowizja = cena_sprzedazy * 0.01
    elif kategoria == "H":
        if inna_prowizja is not None:
            prowizja = cena_sprzedazy * (inna_prowizja / 100)
        else:
            prowizja = 0
    elif kategoria == "I":
        if kategoria_podstawowa == "A":
            prowizja_podstawowa = cena_sprzedazy * 0.0615
        elif kategoria_podstawowa == "B":
            prowizja_podstawowa = cena_sprzedazy * 0.1292
        elif kategoria_podstawowa == "C":
            prowizja_podstawowa = cena_sprzedazy * 0.1292
        elif kategoria_podstawowa == "D":
            prowizja_podstawowa = cena_sprzedazy * 0.1353
        elif kategoria_podstawowa == "E":
            prowizja_podstawowa = cena_sprzedazy * 0.0555
        elif kategoria_podstawowa == "F":
            if cena_sprzedazy <= 60:
                prowizja_podstawowa = cena_sprzedazy * 0.1845
            else:
                prowizja_podstawowa = 11.07 + (cena_sprzedazy - 60) * 0.0984
        elif kategoria_podstawowa == "H":
            if inna_prowizja is not None:
                prowizja_podstawowa = cena_sprzedazy * (inna_prowizja / 100)
            else:
                prowizja_podstawowa = 0
        else:
            prowizja_podstawowa = 0
        
        prowizja = prowizja_podstawowa * 1.6
    else:
        prowizja = 0

    if promowanie and kategoria not in ["G", "I"]:
        prowizja *= 1.75

    return prowizja, prowizja

def oblicz_koszt_wysylki(cena_sprzedazy):
    if cena_sprzedazy < 300:
        return (cena_sprzedazy / 300) * 19.90
    else:
        return 19.90

def oblicz_dostawe_minimalna(cena_sprzedazy):
    if 30 <= cena_sprzedazy < 45:
        return 1.99
    elif 45 <= cena_sprzedazy < 65:
        return 3.99
    elif 65 <= cena_sprzedazy < 100:
        return 5.79
    elif 100 <= cena_sprzedazy < 150:
        return 9.09
    elif cena_sprzedazy >= 150:
        return 11.49
    else:
        return 0

def oblicz_dostawe_maksymalna(cena_sprzedazy):
    if cena_sprzedazy < 100:
        return cena_sprzedazy * 0.0909
    elif 100 <= cena_sprzedazy < 150:
        return 9.09
    else:
        return 11.49

def oblicz_koszt_dostawy_dla_przewoznika(cena_sprzedazy):
    if cena_sprzedazy < 30:
        return {
            'Allegro Paczkomaty InPost': 0,
            'Allegro Automat Pocztex': 0,
            'Allegro One Punkt, Orlen Punkt, DHL BOX': 0,
            'Allegro Kurier UPS': 0,
            'Allegro Kurier DHL (Allegro Delivery)': 0,
            'Allegro Kurier Pocztex': 0,
            'Allegro One Kurier (Allegro Delivery)': 0
        }
    
    if 30 <= cena_sprzedazy < 45:
        return {
            'Allegro Paczkomaty InPost': 1.59,
            'Allegro Automat Pocztex': 1.29,
            'Allegro One Punkt, Orlen Punkt, DHL BOX': 0.99,
            'Allegro Kurier UPS': 1.99,
            'Allegro Kurier DHL (Allegro Delivery)': 1.79,
            'Allegro Kurier Pocztex': 1.99,
            'Allegro One Kurier (Allegro Delivery)': 1.79
        }
    elif 45 <= cena_sprzedazy < 65:
        return {
            'Allegro Paczkomaty InPost': 3.09,
            'Allegro Automat Pocztex': 2.49,
            'Allegro One Punkt, Orlen Punkt, DHL BOX': 1.89,
            'Allegro Kurier UPS': 3.99,
            'Allegro Kurier DHL (Allegro Delivery)': 3.69,
            'Allegro Kurier Pocztex': 3.99,
            'Allegro One Kurier (Allegro Delivery)': 3.69
        }
    elif 65 <= cena_sprzedazy < 100:
        return {
            'Allegro Paczkomaty InPost': 4.99,
            'Allegro Automat Pocztex': 4.29,
            'Allegro One Punkt, Orlen Punkt, DHL BOX': 3.59,
            'Allegro Kurier UPS': 5.79,
            'Allegro Kurier DHL (Allegro Delivery)': 5.39,
            'Allegro Kurier Pocztex': 5.79,
            'Allegro One Kurier (Allegro Delivery)': 5.39
        }
    elif 100 <= cena_sprzedazy < 150:
        return {
            'Allegro Paczkomaty InPost': 7.59,
            'Allegro Automat Pocztex': 6.69,
            'Allegro One Punkt, Orlen Punkt, DHL BOX': 5.89,
            'Allegro Kurier UPS': 9.09,
            'Allegro Kurier DHL (Allegro Delivery)': 8.59,
            'Allegro Kurier Pocztex': 9.09,
            'Allegro One Kurier (Allegro Delivery)': 8.59
        }
    else:  # cena_sprzedazy >= 150
        return {
            'Allegro Paczkomaty InPost': 9.99,
            'Allegro Automat Pocztex': 8.89,
            'Allegro One Punkt, Orlen Punkt, DHL BOX': 7.79,
            'Allegro Kurier UPS': 11.49,
            'Allegro Kurier DHL (Allegro Delivery)': 10.89,
            'Allegro Kurier Pocztex': 11.49,
            'Allegro One Kurier (Allegro Delivery)': 10.89
        }

def oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_procent=None, marza_kwota=None, promowanie=False, inna_prowizja=None, kategoria_podstawowa=None):
    sugerowana_cena = cena_zakupu
    if marza_kwota:
        sugerowana_cena += marza_kwota
    elif marza_procent:
        sugerowana_cena /= (1 - marza_procent / 100)

    for _ in range(10):
        prowizja_min, prowizja_max = oblicz_prowizje(kategoria, sugerowana_cena, promowanie, inna_prowizja, kategoria_podstawowa)
        dostawa_minimalna = oblicz_dostawe_minimalna(sugerowana_cena)
        dostawa_maksymalna = oblicz_dostawe_maksymalna(sugerowana_cena)
        
        opłaty_max = prowizja_max + dostawa_maksymalna

        if marza_kwota:
            nowa_sugerowana_cena = cena_zakupu + opłaty_max + marza_kwota
        elif marza_procent:
            nowa_sugerowana_cena = (cena_zakupu + opłaty_max) / (1 - marza_procent / 100)
        else:
            nowa_sugerowana_cena = cena_zakupu + opłaty_max

        if abs(nowa_sugerowana_cena - sugerowana_cena) < 0.01:
            break

        sugerowana_cena = nowa_sugerowana_cena

    return sugerowana_cena, opłaty_max

@app.route("/", methods=["GET", "POST"])
def index():
    if 'dark_mode' not in session:
        session['dark_mode'] = False
        
    form_marza = KalkulatorMarzyForm()
    form_vat = KalkulatorVATForm()

    # Ustaw domyślną wartość dla checkboxa "Czy smart?" na True
    if not form_marza.czy_smart.data:
        form_marza.czy_smart.data = True

    # Inicjalizacja historii w sesji
    if 'historia_marz' not in session:
        session['historia_marz'] = []

    # Napraw historię - dodaj brakujące pola do starych wpisów
    for wpis in session['historia_marz']:
        if 'koszt_pakowania' not in wpis:
            wpis['koszt_pakowania'] = 0

    if form_marza.submit.data and form_marza.validate():
        cena_zakupu = zamien_przecinek_na_kropke(form_marza.cena_zakupu.data)
        cena_sprzedazy = zamien_przecinek_na_kropke(form_marza.cena_sprzedazy.data)
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

        if kategoria == "H" and inna_prowizja:
            inna_prowizja = zamien_przecinek_na_kropke(inna_prowizja)

        # Tryb nie-smart
        if not czy_smart and kategoria not in ["G", "I"]:
            # Obliczenia dla trybu nie-smart
            cena_sprzedazy_z_dostawa = cena_sprzedazy_total + kwota_dostawy_smart
            
            if kategoria == "H" and inna_prowizja:
                prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_z_dostawa, promowanie=False, inna_prowizja=inna_prowizja)
            else:
                prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_z_dostawa, promowanie=False)
            
            marza_min = cena_sprzedazy_total - cena_zakupu_total - prowizja_min - kwota_dostawy_smart - koszt_pakowania
            marza_max = cena_sprzedazy_total - cena_zakupu_total - prowizja_max - kwota_dostawy_smart - koszt_pakowania
            
            # Obliczanie sugerowanej ceny
            sugerowana_cena_min, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_kwota=marza_kwota, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
            sugerowana_cena_procent, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_procent=marza_procent, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
            
            # Wyniki dla trybu nie-smart
            wynik_bez_promowania = f"""
            <h3>Bez promowania (tryb nie-smart)</h3>
            <div class="wynik">
                <table>
                    <tr>
                        <th>Marża minimalna</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{marza_min:.2f}" style="color:var(--green-color);">
                                {marza_min:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Marża maksymalna</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{marza_max:.2f}" style="color:var(--green-color);">
                                {marza_max:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Prowizja</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{prowizja_min:.2f}" style="color:var(--red-color);">
                                {prowizja_min:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Minimalna sugerowana cena (marża {marza_kwota:.2f} zł)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{sugerowana_cena_min:.2f}" style="color:var(--blue-color);">
                                {sugerowana_cena_min:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Sugerowana cena (marża {marza_procent:.1f}%)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{sugerowana_cena_procent:.2f}" style="color:var(--blue-color);">
                                {sugerowana_cena_procent:.2f} zł
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            """
            
            if ilosc_w_zestawie > 1:
                wynik_bez_promowania += f"""
                <h4>Dla jednej sztuki:</h4>
                <div class="wynik">
                    <table>
                        <tr>
                            <th>Marża minimalna</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_min / ilosc_w_zestawie:.2f}" style="color:var(--green-color);">
                                    {(marza_min / ilosc_w_zestawie):.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża maksymalna</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_max / ilosc_w_zestawie:.2f}" style="color:var(--green-color);">
                                    {(marza_max / ilosc_w_zestawie):.2f} zł
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                """
            
            session['wynik_marza'] = wynik_bez_promowania

        else:
            # Tryb smart
            if kategoria == "G":
                prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=False)
                koszt_wysylki = oblicz_koszt_wysylki(cena_sprzedazy_total)
                maksymalny_koszt = prowizja_max + koszt_wysylki
                marza_darmowa_wysylka = cena_sprzedazy_total - cena_zakupu_total - maksymalny_koszt - koszt_pakowania
                marza_maksymalna = cena_sprzedazy_total - cena_zakupu_total - prowizja_max - koszt_pakowania
                sugerowana_cena = cena_zakupu_total / 0.84

                # Nowe obliczenia dla Ceneo
                prowizja_min_kawa = cena_sprzedazy_total * 0.06
                marza_max_kawa = cena_sprzedazy_total - cena_zakupu_total - prowizja_min_kawa - koszt_pakowania
                prowizja_akcesoria = cena_sprzedazy_total * 0.077
                marza_akcesoria = cena_sprzedazy_total - cena_zakupu_total - prowizja_akcesoria - koszt_pakowania
                prowizja_syropy = cena_sprzedazy_total * 0.0813
                marza_syropy = cena_sprzedazy_total - cena_zakupu_total - prowizja_syropy - koszt_pakowania
                prowizja_max_agd = cena_sprzedazy_total * 0.0882
                marza_min_agd = cena_sprzedazy_total - cena_zakupu_total - prowizja_max_agd - koszt_pakowania

                wynik_html = f"""
                <h3>Wyniki dla kategorii G (Sklep internetowy)</h3>
                <div class="wynik">
                    <table>
                        <tr>
                            <th>Prowizja (bez dostawy)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_max:.2f}" style="color:var(--red-color);">
                                    {prowizja_max:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja z darmową wysyłką</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_max + koszt_wysylki:.2f}" style="color:var(--red-color);">
                                    {(prowizja_max + koszt_wysylki):.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża przy darmowej wysyłce</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_darmowa_wysylka:.2f}" style="color:var(--green-color);">
                                    {marza_darmowa_wysylka:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża maksymalna</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_maksymalna:.2f}" style="color:var(--green-color);">
                                    {marza_maksymalna:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Sugerowana cena sprzedaży</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena:.2f}" style="color:var(--blue-color);">
                                    {sugerowana_cena:.2f} zł
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                <h4>Dodatkowo dla Ceneo:</h4>
                <div class="wynik">
                    <table>
                        <tr>
                            <th>Prowizja minimalna (kawa, herbata)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_min_kawa:.2f}" style="color:var(--red-color);">
                                    {prowizja_min_kawa:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża maksymalna (kawa, herbata)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_max_kawa:.2f}" style="color:var(--green-color);">
                                    {marza_max_kawa:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja akcesoria i słodycze</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_akcesoria:.2f}" style="color:var(--red-color);">
                                    {prowizja_akcesoria:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża akcesoria i słodycze</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_akcesoria:.2f}" style="color:var(--green-color);">
                                    {marza_akcesoria:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja syropy</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_syropy:.2f}" style="color:var(--red-color);">
                                    {prowizja_syropy:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża syropy</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_syropy:.2f}" style="color:var(--green-color);">
                                    {marza_syropy:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja maksymalna (małe AGD)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_max_agd:.2f}" style="color:var(--red-color);">
                                    {prowizja_max_agd:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża minimalna (małe AGD)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_min_agd:.2f}" style="color:var(--green-color);">
                                    {marza_min_agd:.2f} zł
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                """
                
                if ilosc_w_zestawie > 1:
                    wynik_html += f"""
                    <h4>Dla jednej sztuki:</h4>
                    <div class="wynik">
                        <table>
                            <tr>
                                <th>Marża przy darmowej wysyłce</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{marza_darmowa_wysylka / ilosc_w_zestawie:.2f}" style="color:var(--green-color);">
                                        {(marza_darmowa_wysylka / ilosc_w_zestawie):.2f} zł
                                    </span>
                                </td>
                            </tr>
                            <tr>
                                <th>Marża maksymalna</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{marza_maksymalna / ilosc_w_zestawie:.2f}" style="color:var(--green-color);">
                                        {(marza_maksymalna / ilosc_w_zestawie):.2f} zł
                                    </span>
                                </td>
                            </tr>
                        </table>
                    </div>
                    """
                
                session['wynik_marza'] = wynik_html

            else:
                if kategoria == "H" and inna_prowizja:
                    prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=False, inna_prowizja=inna_prowizja)
                elif kategoria == "I":
                    prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=False, kategoria_podstawowa=kategoria_podstawowa)
                else:
                    prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=False)

                dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy_total)
                dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy_total)

                sugerowana_cena_min, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_kwota=marza_kwota, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
                sugerowana_cena_procent, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_procent=marza_procent, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)

                # Oblicz przedział marż dla wszystkich przewoźników
                koszty_dostaw = oblicz_koszt_dostawy_dla_przewoznika(cena_sprzedazy_total)
                marze_przewoznicy = []
                for przewoznik, koszt in koszty_dostaw.items():
                    marza = cena_sprzedazy_total - cena_zakupu_total - prowizja_min - koszt - koszt_pakowania
                    marze_przewoznicy.append(marza)
                
                marza_min_przewoznicy = min(marze_przewoznicy)
                marza_max_przewoznicy = max(marze_przewoznicy)

                # Marża w najgorszej opcji (dostawa maksymalna + prowizja maksymalna)
                marza_najgorsza_opcja = cena_sprzedazy_total - cena_zakupu_total - prowizja_max - dostawa_maksymalna - koszt_pakowania

                wynik_bez_promowania = f"""
                <h3>Bez promowania</h3>
                <div class="wynik">
                    <table>
                        <tr>
                            <th>Marża (przedział dla przewoźników)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_min_przewoznicy:.2f} - {marza_max_przewoznicy:.2f}" 
                                      style="color:var(--green-color);">
                                    {marza_min_przewoznicy:.2f} - {marza_max_przewoznicy:.2f} zł
                                </span>
                                <button class="toggle-tabela" onclick="toggleTabela('tabela-przewoznicy-bez-promowania')" style="margin-left: 10px; padding: 2px 8px; font-size: 12px;">pokaż szczegóły</button>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża w najgorszej opcji</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza_najgorsza_opcja:.2f}" 
                                      style="color:var(--orange-color);">
                                    {marza_najgorsza_opcja:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja czysta (bez dostawy)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_min:.2f}" 
                                      style="color:var(--red-color);">
                                    {prowizja_min:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja z dostawą minimalną</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_min + dostawa_minimalna:.2f}" 
                                      style="color:var(--red-color);">
                                    {(prowizja_min + dostawa_minimalna):.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja z dostawą maksymalną</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_max + dostawa_maksymalna:.2f}" 
                                      style="color:var(--red-color);">
                                    {(prowizja_max + dostawa_maksymalna):.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Minimalna sugerowana cena (marża {marza_kwota:.2f} zł)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena_min:.2f}" 
                                      style="color:var(--blue-color);">
                                    {sugerowana_cena_min:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Sugerowana cena (marża {marza_procent:.1f}%)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena_procent:.2f}" 
                                      style="color:var(--blue-color);">
                                    {sugerowana_cena_procent:.2f} zł
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                """
                
                # Tabela przewoźników dla trybu bez promowania
                tabela_przewoznikow = ""
                for przewoznik, koszt in koszty_dostaw.items():
                    marza = cena_sprzedazy_total - cena_zakupu_total - prowizja_min - koszt - koszt_pakowania
                    tabela_przewoznikow += f"""
                    <tr>
                        <td>{przewoznik}</td>
                        <td>{koszt:.2f} zł</td>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{marza:.2f}" style="color:var(--green-color);">
                                {marza:.2f} zł
                            </span>
                        </td>
                    </tr>
                    """
                
                wynik_przewoznicy = f"""
                <div id="tabela-przewoznicy-bez-promowania" class="rozwijana-tabela" style="display: none;">
                    <h4>Szczegóły marż dla przewoźników (bez promowania)</h4>
                    <div class="wynik">
                        <table>
                            <thead>
                                <tr>
                                    <th>Przewoźnik</th>
                                    <th>Koszt dostawy</th>
                                    <th>Marża</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tabela_przewoznikow}
                            </tbody>
                        </table>
                    </div>
                </div>
                """
                
                if ilosc_w_zestawie > 1:
                    wynik_bez_promowania += f"""
                    <h4>Dla jednej sztuki:</h4>
                    <div class="wynik">
                        <table>
                            <tr>
                                <th>Marża (przedział dla przewoźników)</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{marza_min_przewoznicy / ilosc_w_zestawie:.2f} - {marza_max_przewoznicy / ilosc_w_zestawie:.2f}" 
                                          style="color:var(--green-color);">
                                        {(marza_min_przewoznicy / ilosc_w_zestawie):.2f} - {(marza_max_przewoznicy / ilosc_w_zestawie):.2f} zł
                                    </span>
                                </td>
                            </tr>
                            <tr>
                                <th>Marża w najgorszej opcji</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{marza_najgorsza_opcja / ilosc_w_zestawie:.2f}" 
                                          style="color:var(--orange-color);">
                                        {(marza_najgorsza_opcja / ilosc_w_zestawie):.2f} zł
                                    </span>
                                </td>
                            </tr>
                        </table>
                    </div>
                    """

                if kategoria not in ["G", "I"]:
                    prowizja_min_promo, prowizja_max_promo = oblicz_prowizje(kategoria, cena_sprzedazy_total, promowanie=True, inna_prowizja=inna_prowizja)
                    sugerowana_cena_min_promo, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_kwota=marza_kwota, promowanie=True, inna_prowizja=inna_prowizja)
                    sugerowana_cena_procent_promo, _ = oblicz_sugerowana_cene(cena_zakupu_total, kategoria, marza_procent=marza_procent, promowanie=True, inna_prowizja=inna_prowizja)
                    
                    # Oblicz przedział marż dla wszystkich przewoźników z promowaniem
                    marze_przewoznicy_promo = []
                    for przewoznik, koszt in koszty_dostaw.items():
                        marza = cena_sprzedazy_total - cena_zakupu_total - prowizja_min_promo - koszt - koszt_pakowania
                        marze_przewoznicy_promo.append(marza)
                    
                    marza_min_przewoznicy_promo = min(marze_przewoznicy_promo)
                    marza_max_przewoznicy_promo = max(marze_przewoznicy_promo)
                    
                    # Marża w najgorszej opcji z promowaniem
                    marza_najgorsza_opcja_promo = cena_sprzedazy_total - cena_zakupu_total - prowizja_max_promo - dostawa_maksymalna - koszt_pakowania
                    
                    wynik_z_promowaniem = f"""
                    <h3>Promowanie</h3>
                    <div class="wynik">
                        <table>
                            <tr>
                                <th>Marża (przedział dla przewoźników)</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{marza_min_przewoznicy_promo:.2f} - {marza_max_przewoznicy_promo:.2f}" 
                                          style="color:var(--green-color);">
                                        {marza_min_przewoznicy_promo:.2f} - {marza_max_przewoznicy_promo:.2f} zł
                                    </span>
                                    <button class="toggle-tabela" onclick="toggleTabela('tabela-przewoznicy-z-promowaniem')" style="margin-left: 10px; padding: 2px 8px; font-size: 12px;">pokaż szczegóły</button>
                                </td>
                            </tr>
                            <tr>
                                <th>Marża w najgorszej opcji</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{marza_najgorsza_opcja_promo:.2f}" 
                                          style="color:var(--orange-color);">
                                        {marza_najgorsza_opcja_promo:.2f} zł
                                    </span>
                                </td>
                            </tr>
                            <tr>
                                <th>Prowizja czysta (bez dostawy)</th>
                                <td>
                                    <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                          data-value="{prowizja_min_promo:.2f}" 
                                          style="color:var(--red-color);">
                                        {prowizja_min_promo:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja z dostawą minimalną</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_min_promo + dostawa_minimalna:.2f}" 
                                      style="color:var(--red-color);">
                                    {(prowizja_min_promo + dostawa_minimalna):.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja z dostawą maksymalną</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_max_promo + dostawa_maksymalna:.2f}" 
                                      style="color:var(--red-color);">
                                    {(prowizja_max_promo + dostawa_maksymalna):.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Minimalna sugerowana cena (marża {marza_kwota:.2f} zł)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena_min_promo:.2f}" 
                                      style="color:var(--blue-color);">
                                    {sugerowana_cena_min_promo:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Sugerowana cena (marża {marza_procent:.1f}%)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena_procent_promo:.2f}" 
                                      style="color:var(--blue-color);">
                                    {sugerowana_cena_procent_promo:.2f} zł
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                """
                    
                    # Tabela przewoźników dla trybu z promowaniem
                    tabela_przewoznikow_promo = ""
                    for przewoznik, koszt in koszty_dostaw.items():
                        marza = cena_sprzedazy_total - cena_zakupu_total - prowizja_min_promo - koszt - koszt_pakowania
                        tabela_przewoznikow_promo += f"""
                        <tr>
                            <td>{przewoznik}</td>
                            <td>{koszt:.2f} zł</td>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{marza:.2f}" style="color:var(--green-color);">
                                    {marza:.2f} zł
                                </span>
                            </td>
                        </tr>
                        """
                    
                    wynik_przewoznicy_promo = f"""
                    <div id="tabela-przewoznicy-z-promowaniem" class="rozwijana-tabela" style="display: none;">
                        <h4>Szczegóły marż dla przewoźników (z promowaniem)</h4>
                        <div class="wynik">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Przewoźnik</th>
                                        <th>Koszt dostawy</th>
                                        <th>Marża</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {tabela_przewoznikow_promo}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    """
                    
                    if ilosc_w_zestawie > 1:
                        wynik_z_promowaniem += f"""
                        <h4>Dla jednej sztuki:</h4>
                        <div class="wynik">
                            <table>
                                <tr>
                                    <th>Marża (przedział dla przewoźników)</th>
                                    <td>
                                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                              data-value="{marza_min_przewoznicy_promo / ilosc_w_zestawie:.2f} - {marza_max_przewoznicy_promo / ilosc_w_zestawie:.2f}" 
                                              style="color:var(--green-color);">
                                            {(marza_min_przewoznicy_promo / ilosc_w_zestawie):.2f} - {(marza_max_przewoznicy_promo / ilosc_w_zestawie):.2f} zł
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <th>Marża w najgorszej opcji</th>
                                    <td>
                                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                              data-value="{marza_najgorsza_opcja_promo / ilosc_w_zestawie:.2f}" 
                                              style="color:var(--orange-color);">
                                            {(marza_najgorsza_opcja_promo / ilosc_w_zestawie):.2f} zł
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </div>
                        """
                    
                    session['wynik_marza'] = f"{wynik_bez_promowania}{wynik_przewoznicy}<hr>{wynik_z_promowaniem}{wynik_przewoznicy_promo}"
                else:
                    session['wynik_marza'] = f"{wynik_bez_promowania}{wynik_przewoznicy}"

        # Dodaj do historii
        historia_wpis = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cena_zakupu': cena_zakupu,
            'cena_sprzedazy': cena_sprzedazy,
            'kategoria': kategoria,
            'marza_kwota': marza_kwota,
            'marza_procent': marza_procent,
            'czy_smart': czy_smart,
            'koszt_pakowania': koszt_pakowania
        }
        session['historia_marz'].insert(0, historia_wpis)
        # Zachowaj tylko ostatnie 10 wpisów
        session['historia_marz'] = session['historia_marz'][:10]
        session.modified = True

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
                    if form_vat.typ_kursu_towar.data == 'historyczny':
                        kurs_info_towar = f"Kurs {form_vat.waluta_towar.data} z dnia {form_vat.data_kursu_towar.data}: 1 {form_vat.waluta_towar.data} = {kurs_waluty_towar:.4f} PLN"
                    else:
                        kurs_info_towar = f"Aktualny kurs {form_vat.waluta_towar.data}: 1 {form_vat.waluta_towar.data} = {kurs_waluty_towar:.4f} PLN"
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
                    if form_vat.typ_kursu_dostawa.data == 'historyczny':
                        kurs_info_dostawa = f"Kurs {form_vat.waluta_dostawa.data} z dnia {form_vat.data_kursu_dostawa.data}: 1 {form_vat.waluta_dostawa.data} = {kurs_waluty_dostawa:.4f} PLN"
                    else:
                        kurs_info_dostawa = f"Aktualny kurs {form_vat.waluta_dostawa.data}: 1 {form_vat.waluta_dostawa.data} = {kurs_waluty_dostawa:.4f} PLN"
            
            if kwota_dostawy:
                kwota_dostawy *= kurs_waluty_dostawa
            else:
                koszt_dostawy_sztuka *= kurs_waluty_dostawa

        cena_netto_za_sztuke = cena_netto / ilosc_sztuk

        if kwota_dostawy and ilosc_w_dostawie:
            koszt_dostawy_sztuka = kwota_dostawy / ilosc_w_dostawie

        cena_brutto_za_sztuke = cena_netto_za_sztuke * (1 + vat / 100)
        cena_brutto_z_dostawa_za_sztuke = cena_brutto_za_sztuke + koszt_dostawy_sztuka

        kurs_info_html = ""
        if form_vat.inna_waluta_towar.data or form_vat.inna_waluta_dostawa.data:
            kurs_info_html = "<div style='margin-bottom: 20px;'>"
            if form_vat.inna_waluta_towar.data:
                if kurs_error_towar:
                    kurs_info_html += f"<p style='color:var(--red-color);'><strong>Błąd towaru:</strong> {kurs_error_towar}</p>"
                else:
                    kurs_info_html += f"<p><strong>Towar:</strong> {kurs_info_towar}</p>"
            if form_vat.inna_waluta_dostawa.data:
                if kurs_error_dostawa:
                    kurs_info_html += f"<p style='color:var(--red-color);'><strong>Błąd dostawy:</strong> {kurs_error_dostawa}</p>"
                else:
                    kurs_info_html += f"<p><strong>Dostawa:</strong> {kurs_info_dostawa}</p>"
            kurs_info_html += "</div>"

        session['wynik_vat'] = f"""
        <h3>Wyniki kalkulatora VAT</h3>
        {kurs_info_html}
        <div class="wynik">
            <table>
                <tr>
                    <th>Cena brutto za sztukę:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto_za_sztuke:.2f}" style="color:var(--blue-color);">
                            {cena_brutto_za_sztuke:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena brutto z dostawą za sztukę:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto_z_dostawa_za_sztuke:.2f}" style="color:var(--blue-color);">
                            {cena_brutto_z_dostawa_za_sztuke:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena netto za sztukę:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_netto_za_sztuke:.2f}" style="color:var(--blue-color);">
                            {cena_netto_za_sztuke:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Koszt dostawy na sztukę:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{koszt_dostawy_sztuka:.2f}" style="color:var(--blue-color);">
                            {koszt_dostawy_sztuka:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena brutto całkowita:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto_za_sztuke * ilosc_sztuk:.2f}" style="color:var(--blue-color);">
                            {(cena_brutto_za_sztuke * ilosc_sztuk):.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena brutto z dostawą całkowita:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto_z_dostawa_za_sztuke * ilosc_sztuk:.2f}" style="color:var(--blue-color);">
                            {(cena_brutto_z_dostawa_za_sztuke * ilosc_sztuk):.2f} zł
                        </span>
                    </td>
                </tr>
            </table>
        </div>
        """

    return render_template(
        "index.html",
        form_marza=form_marza,
        form_vat=form_vat,
        wynik_marza=session.get('wynik_marza'),
        wynik_vat=session.get('wynik_vat'),
        historia_marz=session.get('historia_marz', [])
    )

@app.route("/licznik", methods=["GET", "POST"])
def licznik():
    if 'dark_mode' not in session:
        session['dark_mode'] = False
        
    text = ""
    znaki = 0
    slowa = 0
    linie = 0
    
    if request.method == "POST":
        text = request.form.get("tekst", "")
        znaki = len(text)
        slowa = len(text.split()) if text else 0
        linie = len(text.splitlines()) if text else 0

    return render_template(
        "licznik.html",
        text=text,
        znaki=znaki,
        slowa=slowa,
        linie=linie
    )

@app.route("/porownaj", methods=["GET", "POST"])
def porownaj():
    if 'dark_mode' not in session:
        session['dark_mode'] = False
        
    tekst1 = ""
    tekst2 = ""
    roznice = ""
    statystyki1 = {"znaki": 0, "slowa": 0, "linie": 0}
    statystyki2 = {"znaki": 0, "slowa": 0, "linie": 0}
    podobienstwo = 0.0
    
    if request.method == "POST":
        tekst1 = request.form.get("tekst1", "")
        tekst2 = request.form.get("tekst2", "")
        
        # Oblicz statystyki dla tekstu 1
        statystyki1 = {
            "znaki": len(tekst1),
            "slowa": len(tekst1.split()) if tekst1 else 0,
            "linie": len(tekst1.splitlines()) if tekst1 else 0
        }
        
        # Oblicz statystyki dla tekstu 2
        statystyki2 = {
            "znaki": len(tekst2),
            "slowa": len(tekst2.split()) if tekst2 else 0,
            "linie": len(tekst2.splitlines()) if tekst2 else 0
        }
        
        if tekst1 and tekst2:
            # Oblicz podobieństwo między tekstami
            sekwencja = difflib.SequenceMatcher(None, tekst1, tekst2)
            podobienstwo = sekwencja.ratio() * 100  # jako procent
            
            d = difflib.Differ()
            roznice = list(d.compare(
                tekst1.splitlines(), 
                tekst2.splitlines()
            ))
            roznice = "\n".join(roznice)
        elif tekst1 or tekst2:
            # Jeśli tylko jeden tekst, to podobieństwo 0%
            podobienstwo = 0.0
            roznice = ""

    return render_template(
        "porownaj.html",
        tekst1=tekst1,
        tekst2=tekst2,
        roznice=roznice,
        statystyki1=statystyki1,
        statystyki2=statystyki2,
        podobienstwo=podobienstwo
    )

@app.route("/zbiorczy", methods=["GET", "POST"])
def zbiorczy():
    if 'dark_mode' not in session:
        session['dark_mode'] = False
        
    form_zbiorczy = KalkulatorZbiorczyForm()
    wyniki_zbiorcze = None
    laczna_marza = 0
    laczna_cena_zakupu = 0
    laczna_cena_sprzedazy = 0
    liczba_produktow = 0
    
    if form_zbiorczy.submit_zbiorczy.data and form_zbiorczy.validate():
        dane_csv = form_zbiorczy.plik_csv.data
        kategoria = form_zbiorczy.kategoria_zbiorcza.data
        czy_smart = form_zbiorczy.czy_smart_zbiorcze.data
        koszt_pakowania = form_zbiorczy.koszt_pakowania_zbiorcze.data
        
        produkty = przetworz_dane_zbiorcze(dane_csv, kategoria, czy_smart, koszt_pakowania)
        
        if produkty:
            wyniki = []
            for produkt in produkty:
                cena_zakupu = produkt['cena_netto']
                cena_sprzedazy = produkt['cena_brutto']
                
                marza_dane = oblicz_marze_dla_produktu(
                    cena_zakupu, 
                    cena_sprzedazy, 
                    kategoria, 
                    czy_smart, 
                    koszt_pakowania
                )
                
                wyniki.append({
                    'nazwa': produkt['nazwa'],
                    'cena_zakupu': cena_zakupu,
                    'cena_sprzedazy': cena_sprzedazy,
                    'prowizja': marza_dane['prowizja'],
                    'dostawa': marza_dane['dostawa'],
                    'marza_netto': marza_dane['marza_netto'],
                    'marza_procent': marza_dane['marza_procent'],
                    'koszt_pakowania': marza_dane['koszt_pakowania']
                })
                
                laczna_marza += marza_dane['marza_netto']
                laczna_cena_zakupu += cena_zakupu
                laczna_cena_sprzedazy += cena_sprzedazy
                liczba_produktow += 1
            
            wyniki_zbiorcze = wyniki

    return render_template(
        "zbiorczy.html",
        form_zbiorczy=form_zbiorczy,
        wyniki_zbiorcze=wyniki_zbiorcze,
        laczna_marza=laczna_marza,
        laczna_cena_zakupu=laczna_cena_zakupu,
        laczna_cena_sprzedazy=laczna_cena_sprzedazy,
        liczba_produktow=liczba_produktow
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)