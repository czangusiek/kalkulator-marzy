import os
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Optional

app = Flask(__name__)
app.secret_key = 'tajny_klucz'
app.config['SESSION_TYPE'] = 'filesystem'

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
        ('H', 'Inna prowizja')
    ], validators=[DataRequired()])
    inna_prowizja = StringField('Procent prowizji:')
    ilosc_w_zestawie = StringField('Ilość w zestawie:', default="1", validators=[DataRequired()])
    submit = SubmitField('Oblicz')

class KalkulatorVATForm(FlaskForm):
    cena_netto = StringField('Wpisz cenę netto:', validators=[DataRequired()])
    vat = SelectField('Wybierz podatek VAT:', choices=[
        ('5', '5%'),
        ('8', '8%'),
        ('23', '23%')
    ], default="23", validators=[DataRequired()])
    koszt_dostawy_sztuka = StringField('Wpisz koszt dostawy na sztukę:', default="0")
    kwota_dostawy = StringField('Lub wpisz kwotę dostawy:', default="0")
    ilosc_w_dostawie = StringField('Ilość sztuk w dostawie:', default="1", validators=[DataRequired()])
    inna_waluta = BooleanField('Inna waluta niż PLN', default=False)
    kurs_waluty = StringField('Kurs waluty (1 waluta = X PLN):', default="1.0", validators=[Optional()])
    submit = SubmitField('Oblicz')

def zamien_przecinek_na_kropke(liczba):
    return float(liczba.replace(",", "."))

def oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=None):
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
    else:
        prowizja = 0

    if promowanie and kategoria != "G":
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

def oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_procent=None, marza_kwota=None, promowanie=False, inna_prowizja=None):
    sugerowana_cena = cena_zakupu
    if marza_kwota:
        sugerowana_cena += marza_kwota
    elif marza_procent:
        sugerowana_cena /= (1 - marza_procent / 100)

    for _ in range(10):
        prowizja_min, prowizja_max = oblicz_prowizje(kategoria, sugerowana_cena, promowanie, inna_prowizja)
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
        ilosc_w_zestawie = zamien_przecinek_na_kropke(form_marza.ilosc_w_zestawie.data)

        cena_zakupu *= ilosc_w_zestawie
        cena_sprzedazy *= ilosc_w_zestawie

        if kategoria == "H" and inna_prowizja:
            inna_prowizja = zamien_przecinek_na_kropke(inna_prowizja)
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=inna_prowizja)
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
            sugerowana_cena_min, _ = oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_kwota=2, promowanie=False, inna_prowizja=inna_prowizja)
            sugerowana_cena_15, _ = oblicz_sugerowana_cene(cena_zakupu, kategoria, marza_procent=15, promowanie=False, inna_prowizja=inna_prowizja)

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

            if kategoria != "G":
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
                session['wynik_marza'] = f"{wynik_bez_promowania}<hr>{wynik_z_promowaniem}"
            else:
                session['wynik_marza'] = wynik_bez_promowania

    if form_vat.submit.data and form_vat.validate():
        cena_netto = zamien_przecinek_na_kropke(form_vat.cena_netto.data)
        vat = zamien_przecinek_na_kropke(form_vat.vat.data)
        koszt_dostawy_sztuka = zamien_przecinek_na_kropke(form_vat.koszt_dostawy_sztuka.data)
        kwota_dostawy = zamien_przecinek_na_kropke(form_vat.kwota_dostawy.data)
        ilosc_w_dostawie = zamien_przecinek_na_kropke(form_vat.ilosc_w_dostawie.data)
        
        # Obsługa waluty
        inna_waluta = form_vat.inna_waluta.data
        kurs_waluty = 1.0
        if inna_waluta:
            kurs_waluty = zamien_przecinek_na_kropke(form_vat.kurs_waluty.data) if form_vat.kurs_waluty.data else 1.0
        
        # Przeliczanie na PLN jeśli wybrano inną walutę
        if inna_waluta:
            cena_netto *= kurs_waluty
            if kwota_dostawy and ilosc_w_dostawie:
                kwota_dostawy *= kurs_waluty
            else:
                koszt_dostawy_sztuka *= kurs_waluty

        if kwota_dostawy and ilosc_w_dostawie:
            koszt_dostawy_sztuka = kwota_dostawy / ilosc_w_dostawie

        cena_brutto = cena_netto * (1 + vat / 100)
        cena_brutto_z_dostawa = cena_brutto + koszt_dostawy_sztuka

        session['wynik_vat'] = f"""
        <h3>Wyniki kalkulatora VAT</h3>
        <div class="wynik">
            <table>
                <tr>
                    <th>Cena brutto:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto:.2f}" style="color:var(--blue-color);">
                            {cena_brutto:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena brutto z dostawą:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_brutto_z_dostawa:.2f}" style="color:var(--blue-color);">
                            {cena_brutto_z_dostawa:.2f} zł
                        </span>
                    </td>
                </tr>
                <tr>
                    <th>Cena netto:</th>
                    <td>
                        <span class="kwota-do-kopiowania" onclick="kopiujDoSchowka(this)" 
                              data-value="{cena_netto:.2f}" style="color:var(--blue-color);">
                            {cena_netto:.2f} zł
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