import os
from flask import Flask, request, render_template, session, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange

app = Flask(__name__)
app.secret_key = 'tajny_klucz'  # Wymagane przez Flask-WTF i sesję

# Formularz dla pierwszego kalkulatora (marża)
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

# Formularz dla drugiego kalkulatora (VAT)
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
    submit = SubmitField('Oblicz')

# Funkcje pomocnicze
def zamien_przecinek_na_kropke(liczba):
    return float(liczba.replace(",", "."))

def oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=None):
    if kategoria == "A":  # Supermarket
        prowizja = cena_sprzedazy * 0.0615
    elif kategoria == "B":  # Cukier
        prowizja = cena_sprzedazy * 0.1292
    elif kategoria == "C":  # Chemia gospodarcza
        prowizja = cena_sprzedazy * 0.1292
    elif kategoria == "D":  # AGD zwykłe
        prowizja = cena_sprzedazy * 0.1353
    elif kategoria == "E":  # Elektronika
        prowizja = cena_sprzedazy * 0.0555
    elif kategoria == "F":  # Chemia do 60 zł
        if cena_sprzedazy <= 60:
            prowizja = cena_sprzedazy * 0.1845
        else:
            prowizja = 11.07 + (cena_sprzedazy - 60) * 0.0984
    elif kategoria == "G":  # Sklep internetowy
        prowizja = cena_sprzedazy * 0.01  # Prowizja 1%
    elif kategoria == "H":  # Inna prowizja
        if inna_prowizja is not None:
            prowizja = cena_sprzedazy * (inna_prowizja / 100)
        else:
            prowizja = 0  # Domyślnie brak prowizji
    else:
        prowizja = 0  # Domyślnie brak prowizji

    if promowanie and kategoria != "G":  # Kategoria G nie ma promowania
        prowizja *= 1.75  # Zwiększ prowizję o 75% dla ofert promowanych

    return prowizja, prowizja  # Zwróć tę samą wartość dla prowizji minimalnej i maksymalnej

def oblicz_koszt_wysylki(cena_sprzedazy):
    if cena_sprzedazy < 300:
        return (cena_sprzedazy / 300) * 19.90  # Proporcjonalny koszt wysyłki
    else:
        return 19.90  # Stały koszt wysyłki

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
        return 0  # Dla kwot poniżej 30 zł dostawa darmowa

def oblicz_dostawe_maksymalna(cena_sprzedazy):
    if cena_sprzedazy <= 100:
        return cena_sprzedazy * 0.0909
    else:
        return 0  # Dostawa maksymalna tylko dla kwot ≤ 100 zł

def oblicz_sugerowana_cene(cena_zakupu, prowizja_z_dostawa, marza_procent):
    return (cena_zakupu + prowizja_z_dostawa) / (1 - marza_procent / 100)

@app.route("/", methods=["GET", "POST"])
def index():
    form_marza = KalkulatorMarzyForm()
    form_vat = KalkulatorVATForm()

    if form_marza.submit.data and form_marza.validate():
        # Obliczenia dla pierwszego kalkulatora (marża)
        cena_zakupu = zamien_przecinek_na_kropke(form_marza.cena_zakupu.data)
        cena_sprzedazy = zamien_przecinek_na_kropke(form_marza.cena_sprzedazy.data)
        kategoria = form_marza.kategoria.data
        inna_prowizja = form_marza.inna_prowizja.data
        ilosc_w_zestawie = zamien_przecinek_na_kropke(form_marza.ilosc_w_zestawie.data)

        # Mnożenie cen przez ilość sztuk
        cena_zakupu *= ilosc_w_zestawie
        cena_sprzedazy *= ilosc_w_zestawie

        # Obliczenia prowizji i marży (bez promowania)
        if kategoria == "H" and inna_prowizja:
            inna_prowizja = zamien_przecinek_na_kropke(inna_prowizja)
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False, inna_prowizja=inna_prowizja)
        else:
            prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=False)

        if kategoria == "G":  # Sklep internetowy
            koszt_wysylki = oblicz_koszt_wysylki(cena_sprzedazy)
            maksymalny_koszt = prowizja_max + koszt_wysylki
            marza_darmowa_wysylka = cena_sprzedazy - cena_zakupu - maksymalny_koszt
            marza_maksymalna = cena_sprzedazy - cena_zakupu - prowizja_max
            sugerowana_cena = cena_zakupu / 0.84  # Sugerowana cena dla 15% marży

            wynik_marza = (
                f"<h3>Wyniki dla kategorii G (Sklep internetowy)</h3>"
                f"<table>"
                f"<tr><th>Maksymalny koszt (przy darmowej wysyłce)</th><td><strong style='color:red;'>{maksymalny_koszt:.2f}</strong> zł</td></tr>"
                f"<tr><th>Marża przy darmowej wysyłce</th><td><strong style='color:green;'>{marza_darmowa_wysylka:.2f}</strong> zł</td></tr>"
                f"<tr><th>Marża maksymalna</th><td><strong style='color:green;'>{marza_maksymalna:.2f}</strong> zł</td></tr>"
                f"<tr><th>Sugerowana cena sprzedaży na sklepie</th><td><strong style='color:blue;'>{sugerowana_cena:.2f}</strong> zł</td></tr>"
                f"</table>"
            )
        else:
            # Obliczenia dostawy
            dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy)
            dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy)

            # Obliczenia sugerowanych cen (bez promowania)
            prowizja_z_dostawa_min = prowizja_min + dostawa_minimalna
            prowizja_z_dostawa_max = prowizja_max + dostawa_maksymalna

            if cena_sprzedazy > 100:
                prowizja_z_dostawa_max = prowizja_z_dostawa_min

            sugerowana_cena_min = cena_zakupu + prowizja_z_dostawa_min + 2
            sugerowana_cena_15 = oblicz_sugerowana_cene(cena_zakupu, prowizja_z_dostawa_min, 15)

            # Wyniki bez promowania
            wynik_bez_promowania = (
                f"<h3>Bez promowania</h3>"
                f"<table>"
                f"<tr><th>Marża (dostawa minimalna)</th><td><strong style='color:green;'>{cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_min:.2f}</strong> zł</td></tr>"
                f"<tr><th>Marża (dostawa maksymalna)</th><td><strong style='color:green;'>{cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_max:.2f}</strong> zł</td></tr>"
                f"<tr><th>Prowizja z dostawą minimalną</th><td><strong style='color:red;'>{prowizja_z_dostawa_min:.2f}</strong> zł</td></tr>"
                f"<tr><th>Prowizja z dostawą maksymalną</th><td><strong style='color:red;'>{prowizja_z_dostawa_max:.2f}</strong> zł</td></tr>"
                f"<tr><th>Minimalna sugerowana cena sprzedaży (marża 2 zł)</th><td><strong style='color:blue;'>{sugerowana_cena_min:.2f}</strong> zł</td></tr>"
                f"<tr><th>Sugerowana cena sprzedaży (marża 15%)</th><td><strong style='color:blue;'>{sugerowana_cena_15:.2f}</strong> zł</td></tr>"
                f"</table>"
            )

            # Obliczenia prowizji i marży (z promowaniem)
            if kategoria != "G":  # Kategoria G nie ma promowania
                if kategoria == "H" and inna_prowizja:
                    prowizja_min_promo, prowizja_max_promo = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=True, inna_prowizja=inna_prowizja)
                else:
                    prowizja_min_promo, prowizja_max_promo = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=True)

                # Obliczenia sugerowanych cen (z promowaniem)
                prowizja_z_dostawa_min_promo = prowizja_min_promo + dostawa_minimalna
                prowizja_z_dostawa_max_promo = prowizja_max_promo + dostawa_maksymalna

                if cena_sprzedazy > 100:
                    prowizja_z_dostawa_max_promo = prowizja_z_dostawa_min_promo

                sugerowana_cena_min_promo = cena_zakupu + prowizja_z_dostawa_min_promo + 2
                sugerowana_cena_15_promo = oblicz_sugerowana_cene(cena_zakupu, prowizja_z_dostawa_min_promo, 15)

                # Wyniki z promowaniem
                wynik_z_promowaniem = (
                    f"<h3>Promowanie</h3>"
                    f"<table>"
                    f"<tr><th>Marża (dostawa minimalna)</th><td><strong style='color:green;'>{cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_min_promo:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Marża (dostawa maksymalna)</th><td><strong style='color:green;'>{cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_max_promo:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Prowizja z dostawą minimalną</th><td><strong style='color:red;'>{prowizja_z_dostawa_min_promo:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Prowizja z dostawą maksymalną</th><td><strong style='color:red;'>{prowizja_z_dostawa_max_promo:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Minimalna sugerowana cena sprzedaży (marża 2 zł)</th><td><strong style='color:blue;'>{sugerowana_cena_min_promo:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Sugerowana cena sprzedaży (marża 15%)</th><td><strong style='color:blue;'>{sugerowana_cena_15_promo:.2f}</strong> zł</td></tr>"
                    f"</table>"
                )

                # Połącz wyniki
                session['wynik_marza'] = f"{wynik_bez_promowania}<hr>{wynik_z_promowaniem}"
            else:
                session['wynik_marza'] = wynik_bez_promowania

    if form_vat.submit.data and form_vat.validate():
        # Obliczenia dla drugiego kalkulatora (VAT)
        cena_netto = zamien_przecinek_na_kropke(form_vat.cena_netto.data)
        vat = zamien_przecinek_na_kropke(form_vat.vat.data)
        koszt_dostawy_sztuka = zamien_przecinek_na_kropke(form_vat.koszt_dostawy_sztuka.data)
        kwota_dostawy = zamien_przecinek_na_kropke(form_vat.kwota_dostawy.data)
        ilosc_w_dostawie = zamien_przecinek_na_kropke(form_vat.ilosc_w_dostawie.data)

        if kwota_dostawy and ilosc_w_dostawie:
            koszt_dostawy_sztuka = kwota_dostawy / ilosc_w_dostawie

        cena_brutto = cena_netto * (1 + vat / 100)
        cena_brutto_z_dostawa = cena_brutto + koszt_dostawy_sztuka

        # Wyniki
        session['wynik_vat'] = (
            f"<h3>Wyniki kalkulatora VAT</h3>"
            f"<p><strong>Cena brutto:</strong> {cena_brutto:.2f} zł</p>"
            f"<p><strong>Cena brutto z dostawą:</strong> {cena_brutto_z_dostawa:.2f} zł</p>"
        )

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