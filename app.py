import os
from flask import Flask, request, render_template

app = Flask(__name__)

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

    if promowanie:
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
    # Oblicza sugerowaną cenę sprzedaży, uwzględniając marżę procentową po odliczeniu prowizji z dostawą
    return (cena_zakupu + prowizja_z_dostawa) / (1 - marza_procent / 100)

@app.route("/", methods=["GET", "POST"])
def index():
    wynik = None
    cena_zakupu_input = ""
    cena_sprzedazy_input = ""
    kategoria_input = ""
    inna_prowizja_input = ""
    ilosc_sztuk_input = "1"  # Domyślna wartość dla ilości sztuk

    # Dane dla drugiego kalkulatora
    wynik_vat = None
    cena_netto_input = ""
    vat_input = "23"
    koszt_dostawy_sztuka_input = "0"
    kwota_dostawy_input = "0"
    ilosc_sztuk_vat_input = "1"

    if request.method == "POST":
        if "cena_zakupu" in request.form:  # Pierwszy kalkulator
            cena_zakupu = zamien_przecinek_na_kropke(request.form["cena_zakupu"])
            cena_sprzedazy = zamien_przecinek_na_kropke(request.form["cena_sprzedazy"])
            kategoria = request.form["kategoria"]
            inna_prowizja = request.form.get("inna_prowizja", None)
            ilosc_sztuk = zamien_przecinek_na_kropke(request.form.get("ilosc_sztuk", "1"))

            # Zapisz wprowadzone dane, aby przekazać je z powrotem do formularza
            cena_zakupu_input = request.form["cena_zakupu"]
            cena_sprzedazy_input = request.form["cena_sprzedazy"]
            kategoria_input = kategoria
            inna_prowizja_input = inna_prowizja if inna_prowizja else ""
            ilosc_sztuk_input = request.form.get("ilosc_sztuk", "1")

            # Mnożenie cen przez ilość sztuk
            cena_zakupu *= ilosc_sztuk
            cena_sprzedazy *= ilosc_sztuk

            # Oblicz prowizje minimalną i maksymalną (bez promowania)
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

                wynik = (
                    f"<h3>Wyniki dla kategorii G (Sklep internetowy)</h3>"
                    f"<table>"
                    f"<tr><th>Maksymalny koszt (przy darmowej wysyłce)</th><td><strong style='color:red;'>{maksymalny_koszt:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Marża przy darmowej wysyłce</th><td><strong style='color:green;'>{marza_darmowa_wysylka:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Marża maksymalna</th><td><strong style='color:green;'>{marza_maksymalna:.2f}</strong> zł</td></tr>"
                    f"<tr><th>Sugerowana cena sprzedaży na sklepie</th><td><strong style='color:blue;'>{sugerowana_cena:.2f}</strong> zł</td></tr>"
                    f"</table>"
                )
            else:
                # Oblicz koszty dostawy
                dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy)
                dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy)

                # Oblicz prowizję z dostawą (bez promowania)
                prowizja_z_dostawa_min = prowizja_min + dostawa_minimalna
                prowizja_z_dostawa_max = prowizja_max + dostawa_maksymalna

                # Dla kwot powyżej 100 zł prowizja i marża maksymalna są takie same jak minimalna
                if cena_sprzedazy > 100:
                    prowizja_z_dostawa_max = prowizja_z_dostawa_min

                # Oblicz sugerowane ceny sprzedaży (bez promowania)
                sugerowana_cena_min = cena_zakupu + prowizja_z_dostawa_min + 2  # Minimalna cena (marża 2 zł)
                sugerowana_cena_15 = oblicz_sugerowana_cene(cena_zakupu, prowizja_z_dostawa_min, 15)  # Marża 15%

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

                # Oblicz prowizje minimalną i maksymalną (z promowaniem)
                if kategoria == "H" and inna_prowizja:
                    prowizja_min_promo, prowizja_max_promo = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=True, inna_prowizja=inna_prowizja)
                else:
                    prowizja_min_promo, prowizja_max_promo = oblicz_prowizje(kategoria, cena_sprzedazy, promowanie=True)

                # Oblicz prowizję z dostawą (z promowaniem)
                prowizja_z_dostawa_min_promo = prowizja_min_promo + dostawa_minimalna
                prowizja_z_dostawa_max_promo = prowizja_max_promo + dostawa_maksymalna

                # Dla kwot powyżej 100 zł prowizja i marża maksymalna są takie same jak minimalna
                if cena_sprzedazy > 100:
                    prowizja_z_dostawa_max_promo = prowizja_z_dostawa_min_promo

                # Oblicz sugerowane ceny sprzedaży (z promowaniem)
                sugerowana_cena_min_promo = cena_zakupu + prowizja_z_dostawa_min_promo + 2  # Minimalna cena (marża 2 zł)
                sugerowana_cena_15_promo = oblicz_sugerowana_cene(cena_zakupu, prowizja_z_dostawa_min_promo, 15)  # Marża 15%

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
                wynik = f"{wynik_bez_promowania}<hr>{wynik_z_promowaniem}"

        elif "cena_netto" in request.form:  # Drugi kalkulator
            cena_netto = zamien_przecinek_na_kropke(request.form["cena_netto"])
            vat = zamien_przecinek_na_kropke(request.form["vat"])
            koszt_dostawy_sztuka = zamien_przecinek_na_kropke(request.form.get("koszt_dostawy_sztuka", "0"))
            kwota_dostawy = zamien_przecinek_na_kropke(request.form.get("kwota_dostawy", "0"))
            ilosc_sztuk = zamien_przecinek_na_kropke(request.form.get("ilosc_sztuk", "1"))

            # Zapisz wprowadzone dane, aby przekazać je z powrotem do formularza
            cena_netto_input = request.form["cena_netto"]
            vat_input = request.form["vat"]
            koszt_dostawy_sztuka_input = request.form.get("koszt_dostawy_sztuka", "0")
            kwota_dostawy_input = request.form.get("kwota_dostawy", "0")
            ilosc_sztuk_vat_input = request.form.get("ilosc_sztuk", "1")

            # Oblicz koszt dostawy na sztukę
            if kwota_dostawy and ilosc_sztuk:
                koszt_dostawy_sztuka = kwota_dostawy / ilosc_sztuk

            # Oblicz cenę brutto
            cena_brutto = cena_netto * (1 + vat / 100)

            # Oblicz cenę brutto z dostawą
            cena_brutto_z_dostawa = cena_brutto + koszt_dostawy_sztuka

            # Wyniki dla drugiego kalkulatora
            wynik_vat = (
                f"<h3>Wyniki kalkulatora VAT</h3>"
                f"<p><strong>Cena brutto:</strong> {cena_brutto:.2f} zł</p>"
                f"<p><strong>Cena brutto z dostawą:</strong> {cena_brutto_z_dostawa:.2f} zł</p>"
            )

    return render_template(
        "index.html",
        wynik=wynik,
        cena_zakupu_input=cena_zakupu_input,
        cena_sprzedazy_input=cena_sprzedazy_input,
        kategoria_input=kategoria_input,
        inna_prowizja_input=inna_prowizja_input,
        ilosc_sztuk_input=ilosc_sztuk_input,
        wynik_vat=wynik_vat,
        cena_netto_input=cena_netto_input,
        vat_input=vat_input,
        koszt_dostawy_sztuka_input=koszt_dostawy_sztuka_input,
        kwota_dostawy_input=kwota_dostawy_input,
        ilosc_sztuk_vat_input=ilosc_sztuk_vat_input
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Użyj portu z zmiennej środowiskowej PORT lub 5000 jako domyślny
    app.run(host="0.0.0.0", port=port)