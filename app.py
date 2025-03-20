from flask import Flask, request, render_template, redirect, url_for

app = Flask(__name__)

def zamien_przecinek_na_kropke(liczba):
    return float(liczba.replace(",", "."))

def oblicz_prowizje(kategoria, cena_sprzedazy):
    if kategoria == "A":  # Supermarket
        return cena_sprzedazy * 0.0615
    elif kategoria == "B":  # Cukier
        return cena_sprzedazy * 0.1292
    elif kategoria == "C":  # Chemia gospodarcza
        return cena_sprzedazy * 0.1292
    elif kategoria == "D":  # AGD zwykłe
        return cena_sprzedazy * 0.1353
    elif kategoria == "E":  # Elektronika
        return cena_sprzedazy * 0.0555
    elif kategoria == "F":  # Chemia do 60 zł
        if cena_sprzedazy <= 60:
            return cena_sprzedazy * 0.1845
        else:
            return 11.07 + (cena_sprzedazy - 60) * 0.0984
    elif kategoria == "G":  # Sklep internetowy
        return cena_sprzedazy * 0.01  # Prowizja 1%
    else:
        return 0  # Domyślnie brak prowizji

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

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        cena_zakupu = zamien_przecinek_na_kropke(request.form["cena_zakupu"])
        cena_sprzedazy = zamien_przecinek_na_kropke(request.form["cena_sprzedazy"])
        kategoria = request.form["kategoria"]

        prowizja = oblicz_prowizje(kategoria, cena_sprzedazy)

        if kategoria == "G":  # Sklep internetowy
            koszt_wysylki = oblicz_koszt_wysylki(cena_sprzedazy)
            maksymalny_koszt = prowizja + koszt_wysylki
            marza_darmowa_wysylka = cena_sprzedazy - cena_zakupu - maksymalny_koszt
            marza_maksymalna = cena_sprzedazy - cena_zakupu - prowizja
            sugerowana_cena = cena_zakupu / 0.84  # Sugerowana cena dla 15% marży

            wynik = (
                f"Maksymalny koszt (przy darmowej wysyłce): {maksymalny_koszt:.2f} zł\n"
                f"Marża przy darmowej wysyłce: {marza_darmowa_wysylka:.2f} zł\n"
                f"Marża maksymalna: {marza_maksymalna:.2f} zł\n"
                f"Sugerowana cena sprzedaży na sklepie: {sugerowana_cena:.2f} zł"
            )
        else:
            dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy)
            dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy)

            if cena_sprzedazy < 30:
                marza = cena_sprzedazy - cena_zakupu - dostawa_maksymalna - prowizja
                wynik = f"Marża (dostawa maksymalna): {marza:.2f} zł"
            elif 30 <= cena_sprzedazy <= 100:
                marza_dla_1_sztuki = cena_sprzedazy - cena_zakupu - dostawa_minimalna - prowizja
                marza_minimalna = cena_sprzedazy - cena_zakupu - dostawa_maksymalna - prowizja
                wynik = (
                    f"Marża dla 1 sztuki (dostawa minimalna): {marza_dla_1_sztuki:.2f} zł\n"
                    f"Marża minimalna (dostawa maksymalna): {marza_minimalna:.2f} zł"
                )
            else:
                marza = cena_sprzedazy - cena_zakupu - dostawa_minimalna - prowizja
                wynik = f"Marża (dostawa minimalna): {marza:.2f} zł"

        return render_template("wynik.html", wynik=wynik)
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)