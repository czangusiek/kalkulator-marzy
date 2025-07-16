import os
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import datetime, timedelta
import requests

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

def zamien_przecinek_na_kropke(liczba):
    if isinstance(liczba, str):
        return float(liczba.replace(",", "."))
    return liczba

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

    if form_marza.submit.data and form_marza.validate():
        cena_zakupu = zamien_przecinek_na_kropke(form_marza.cena_zakupu.data)
        cena_sprzedazy = zamien_przecinek_na_kropke(form_marza.cena_sprzedazy.data)
        kategoria = form_marza.kategoria.data
        inna_prowizja = form_marza.inna_prowizja.data
        kategoria_podstawowa = form_marza.kategoria_podstawowa.data if kategoria == "I" else None
        ilosc_w_zestawie = zamien_przecinek_na_kropke(form_marza.ilosc_w_zestawie.data)

        cena_zakupu *= ilosc_w_zestawie
        cena_sprzedazy *= ilosc_w_zestawie

        if kategoria == "H" and inna_prowizja:
            inna_prowizja = zamien_przecinek_na_kropke(inna_prowizja)
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=inna_prowizja)
        elif kategoria == "I":
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, kategoria_podstawowa=kategoria_podstawowa)
        else:
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False)

        dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy)
        dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy)

        if kategoria == "G":
            koszt_wysylki = oblicz_koszt_wysylki(cena_sprzedazy)
            maksymalny_koszt = prowizja_max + koszt_wysylki
            marza_darmowa_wysylka = cena_sprzedazy - cena_zakupu - maksymalny_koszt
            marza_maksymalna = cena_sprzedazy - cena_zakupu - prowizja_max
            sugerowana_cena = cena_zakupu / 0.84

            session['wynik_marza'] = f"""
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
                                {prowizja_max + koszt_wysylki:.2f} zł
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
            """
        else:
            sugerowana_cena_min, _ = oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_kwota=2, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)
            sugerowana_cena_15, _ = oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_procent=15, promowanie=False, inna_prowizja=inna_prowizja, kategoria_podstawowa=kategoria_podstawowa)

            wynik_bez_promowania = f"""
            <h3>Bez promowania</h3>
            <div class="wynik">
                <table>
                    <tr>
                        <th>Marża (dostawa minimalna)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{cena_sprzedazy - cena_zakupu - prowizja_min - dostawa_minimalna:.2f}" 
                                  style="color:var(--green-color);">
                                {cena_sprzedazy - cena_zakupu - prowizja_min - dostawa_minimalna:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Marża (dostawa maksymalna)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{cena_sprzedazy - cena_zakupu - prowizja_max - dostawa_maksymalna:.2f}" 
                                  style="color:var(--green-color);">
                                {cena_sprzedazy - cena_zakupu - prowizja_max - dostawa_maksymalna:.2f} zł
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
                                {prowizja_min + dostawa_minimalna:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Prowizja z dostawą maksymalną</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{prowizja_max + dostawa_maksymalna:.2f}" 
                                  style="color:var(--red-color);">
                                {prowizja_max + dostawa_maksymalna:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Minimalna sugerowana cena (marża 2 zł)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{sugerowana_cena_min:.2f}" 
                                  style="color:var(--blue-color);">
                                {sugerowana_cena_min:.2f} zł
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <th>Sugerowana cena (marża 15%)</th>
                        <td>
                            <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                  data-value="{sugerowana_cena_15:.2f}" 
                                  style="color:var(--blue-color);">
                                {sugerowana_cena_15:.2f} zł
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            """

            if kategoria not in ["G", "I"]:
                prowizja_min_promo, prowizja_max_promo = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=True, inna_prowizja=inna_prowizja)
                sugerowana_cena_min_promo, _ = oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_kwota=2, promowanie=True, inna_prowizja=inna_prowizja)
                sugerowana_cena_15_promo, _ = oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_procent=15, promowanie=True, inna_prowizja=inna_prowizja)
                
                wynik_z_promowaniem = f"""
                <h3>Promowanie</h3>
                <div class="wynik">
                    <table>
                        <tr>
                            <th>Marża (dostawa minimalna)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{cena_sprzedazy - cena_zakupu - prowizja_min_promo - dostawa_minimalna:.2f}" 
                                      style="color:var(--green-color);">
                                    {cena_sprzedazy - cena_zakupu - prowizja_min_promo - dostawa_minimalna:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Marża (dostawa maksymalna)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{cena_sprzedazy - cena_zakupu - prowizja_max_promo - dostawa_maksymalna:.2f}" 
                                      style="color:var(--green-color);">
                                    {cena_sprzedazy - cena_zakupu - prowizja_max_promo - dostawa_maksymalna:.2f} zł
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
                                    {prowizja_min_promo + dostawa_minimalna:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Prowizja z dostawą maksymalną</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{prowizja_max_promo + dostawa_maksymalna:.2f}" 
                                      style="color:var(--red-color);">
                                    {prowizja_max_promo + dostawa_maksymalna:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Minimalna sugerowana cena (marża 2 zł)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena_min_promo:.2f}" 
                                      style="color:var(--blue-color);">
                                    {sugerowana_cena_min_promo:.2f} zł
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>Sugerowana cena (marża 15%)</th>
                            <td>
                                <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                                      data-value="{sugerowana_cena_15_promo:.2f}" 
                                      style="color:var(--blue-color);">
                                    {sugerowana_cena_15_promo:.2f} zł
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                """
                
                # Tabela marż dla przewoźników (tylko bez promowania)
                koszty_dostaw = oblicz_koszt_dostawy_dla_przewoznika(cena_sprzedazy)
                tabela_przewoznikow = ""
                for przewoznik, koszt in koszty_dostaw.items():
                    marza = cena_sprzedazy - cena_zakupu - prowizja_min - koszt
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
                <h4>Marża dla poszczególnych przewoźników (bez promowania)</h4>
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
                """
                
                session['wynik_marza'] = f"{wynik_bez_promowania}{wynik_przewoznicy}<hr>{wynik_z_promowaniem}"
            else:
                # Tabela marż dla przewoźników dla kategorii I
                koszty_dostaw = oblicz_koszt_dostawy_dla_przewoznika(cena_sprzedazy)
                tabela_przewoznikow = ""
                for przewoznik, koszt in koszty_dostaw.items():
                    marza = cena_sprzedazy - cena_zakupu - prowizja_min - koszt
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
                <h4>Marża dla poszczególnych przewoźników (bez promowania)</h4>
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
                """
                session['wynik_marza'] = f"{wynik_bez_promowania}{wynik_przewoznicy}"

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
                            {cena_brutto_za_sztuke * ilosc_sztuk:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena brutto z dostawą całkowita:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto_z_dostawa_za_sztuke * ilosc_sztuk:.2f}" style="color:var(--blue-color);">
                            {cena_brutto_z_dostawa_za_sztuke * ilosc_sztuk:.2f} zł
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
        wynik_vat=session.get('wynik_vat')
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)