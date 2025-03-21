import os
from flask import Flask, request, render_template

app = Flask(__name__)

def zamien_przecinek_na_kropke(liczba):
    return float(liczba.replace(",", "."))

def oblicz_prowizje(kategoria, cena_sprzedazy):
    if kategoria == "A":  # Supermarket
        return cena_sprzedazy * 0.0615, cena_sprzedazy * 0.0615  # Maksymalna i minimalna prowizja
    elif kategoria == "B":  # Cukier
        return cena_sprzedazy * 0.1292, cena_sprzedazy * 0.1292
    elif kategoria == "C":  # Chemia gospodarcza
        return cena_sprzedazy * 0.1292, cena_sprzedazy * 0.1292
    elif kategoria == "D":  # AGD zwykłe
        return cena_sprzedazy * 0.1353, cena_sprzedazy * 0.1353
    elif kategoria == "E":  # Elektronika
        return cena_sprzedazy * 0.0555, cena_sprzedazy * 0.0555
    elif kategoria == "F":  # Chemia do 60 zł
        if cena_sprzedazy <= 60:
            return cena_sprzedazy * 0.1845, cena_sprzedazy * 0.1845
        else:
            return 11.07 + (cena_sprzedazy - 60) * 0.0984, 11.07 + (cena_sprzedazy - 60) * 0.0984
    elif kategoria == "G":  # Sklep internetowy
        return cena_sprzedazy * 0.01, cena_sprzedazy * 0.01  # Prowizja 1%
    else:
        return 0, 0  # Domyślnie brak prowizji

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

    if request.method == "POST":
        cena_zakupu = zamien_przecinek_na_kropke(request.form["cena_zakupu"])
        cena_sprzedazy = zamien_przecinek_na_kropke(request.form["cena_sprzedazy"])
        kategoria = request.form["kategoria"]

        # Zapisz wprowadzone dane, aby przekazać je z powrotem do formularza
        cena_zakupu_input = request.form["cena_zakupu"]
        cena_sprzedazy_input = request.form["cena_sprzedazy"]
        kategoria_input = kategoria

        # Oblicz prowizje minimalną i maksymalną
        prowizja_min, prowizja_max = oblicz_prowizje(kategoria, cena_sprzedazy)

        if kategoria == "G":  # Sklep internetowy
            koszt_wysylki = oblicz_koszt_wysylki(cena_sprzedazy)
            maksymalny_koszt = prowizja_max + koszt_wysylki
            marza_darmowa_wysylka = cena_sprzedazy - cena_zakupu - maksymalny_koszt
            marza_maksymalna = cena_sprzedazy - cena_zakupu - prowizja_max
            sugerowana_cena = cena_zakupu / 0.84  # Sugerowana cena dla 15% marży

            wynik = (
                f"<div>Maksymalny koszt (przy darmowej wysyłce): <strong style='color:red;'>{maksymalny_koszt:.2f}</strong> zł</div><br>"
                f"<div>Marża przy darmowej wysyłce: <strong style='color:green;'>{marza_darmowa_wysylka:.2f}</strong> zł</div><br>"
                f"<div>Marża maksymalna: <strong style='color:green;'>{marza_maksymalna:.2f}</strong> zł</div><br>"
                f"<div>Sugerowana cena sprzedaży na sklepie: <strong style='color:blue;'>{sugerowana_cena:.2f}</strong> zł</div>"
            )
        else:
            # Oblicz koszty dostawy
            dostawa_minimalna = oblicz_dostawe_minimalna(cena_sprzedazy)
            dostawa_maksymalna = oblicz_dostawe_maksymalna(cena_sprzedazy)

            # Oblicz prowizję z dostawą
            prowizja_z_dostawa_min = prowizja_min + dostawa_minimalna
            prowizja_z_dostawa_max = prowizja_max + dostawa_maksymalna

            # Wybierz najwyższą prowizję z dostawą
            if cena_sprzedazy <= 100:
                prowizja_z_dostawa = prowizja_z_dostawa_max  # Dla kwot ≤ 100 zł używamy dostawy maksymalnej
            else:
                prowizja_z_dostawa = prowizja_z_dostawa_min  # Dla kwot > 100 zł używamy dostawy minimalnej

            # Oblicz sugerowane ceny sprzedaży
            sugerowana_cena_min = cena_zakupu + prowizja_z_dostawa + 2  # Minimalna cena (marża 2 zł)
            sugerowana_cena_15 = oblicz_sugerowana_cene(cena_zakupu, prowizja_z_dostawa, 15)  # Marża 15%

            if cena_sprzedazy < 30:
                marza = cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_max
                wynik = (
                    f"<div>Marża (dostawa maksymalna): <strong style='color:green;'>{marza:.2f}</strong> zł</div><br>"
                    f"<div>Prowizja z dostawą maksymalną: <strong style='color:red;'>{prowizja_z_dostawa_max:.2f}</strong> zł</div><br>"
                    f"<div>Minimalna sugerowana cena sprzedaży (marża 2 zł): <strong style='color:blue;'>{sugerowana_cena_min:.2f}</strong> zł</div><br>"
                    f"<div>Sugerowana cena sprzedaży (marża 15%): <strong style='color:blue;'>{sugerowana_cena_15:.2f}</strong> zł</div>"
                )
            elif 30 <= cena_sprzedazy <= 100:
                marza_dla_1_sztuki = cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_min
                marza_minimalna = cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_max
                wynik = (
                    f"<div>Marża dla 1 sztuki (dostawa minimalna): <strong style='color:green;'>{marza_dla_1_sztuki:.2f}</strong> zł</div><br>"
                    f"<div>Marża minimalna (dostawa maksymalna): <strong style='color:green;'>{marza_minimalna:.2f}</strong> zł</div><br>"
                    f"<div>Prowizja z dostawą minimalną: <strong style='color:red;'>{prowizja_z_dostawa_min:.2f}</strong> zł</div><br>"
                    f"<div>Prowizja z dostawą maksymalną: <strong style='color:red;'>{prowizja_z_dostawa_max:.2f}</strong> zł</div><br>"
                    f"<div>Minimalna sugerowana cena sprzedaży (marża 2 zł): <strong style='color:blue;'>{sugerowana_cena_min:.2f}</strong> zł</div><br>"
                    f"<div>Sugerowana cena sprzedaży (marża 15%): <strong style='color:blue;'>{sugerowana_cena_15:.2f}</strong> zł</div>"
                )
            else:
                marza = cena_sprzedazy - cena_zakupu - prowizja_z_dostawa_min
                wynik = (
                    f"<div>Marża (dostawa minimalna): <strong style='color:green;'>{marza:.2f}</strong> zł</div><br>"
                    f"<div>Prowizja z dostawą minimalną: <strong style='color:red;'>{prowizja_z_dostawa_min:.2f}</strong> zł</div><br>"
                    f"<div>Minimalna sugerowana cena sprzedaży (marża 2 zł): <strong style='color:blue;'>{sugerowana_cena_min:.2f}</strong> zł</div><br>"
                    f"<div>Sugerowana cena sprzedaży (marża 15%): <strong style='color:blue;'>{sugerowana_cena_15:.2f}</strong> zł</div>"
                )

    return render_template(
        "index.html",
        wynik=wynik,
        cena_zakupu_input=cena_zakupu_input,
        cena_sprzedazy_input=cena_sprzedazy_input,
        kategoria_input=kategoria_input
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Użyj portu z zmiennej środowiskowej PORT lub 5000 jako domyślny
    app.run(host="0.0.0.0", port=port)