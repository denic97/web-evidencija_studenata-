from flask import Flask, render_template, url_for, request, redirect, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import io
import csv
import ast
import mariadb
import pymsgbox

app = Flask(__name__)

# KONFIGURACIJA MAIL-A

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USERNAME"] = "evidencija.atvss@gmail.com"
app.config["MAIL_PASSWORD"] = "atvss123loz"
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
mail = Mail(app)

def send_email(ime, prezime, email, lozinka):
   msg = Message(
       subject="Korisnički nalog",
       sender="ATVSS Evidencija studenata",
       recipients=[email],
   )
   msg.html = render_template("email.html", ime=ime, prezime=prezime, lozinka=lozinka)
   mail.send(msg)
   return "Sent"


#! ***********************************************
#! KONEKCIJA SA BAZOM
#! konekcija =MySQLdb.connect(
#! user="root",
#! host="localhost",
#! database="evidencija_studenata"
#! )
#! kursor = konekcija.cursor()
#! **********************************************


# KONEKCIJA SA BAZOM
konekcija = mariadb.connect(
    user="root",
    password="",
    host="localhost",
    port=3307,
    database="evidencija_studenata"
)
kursor = konekcija.cursor(dictionary=True)

# SESIJA
app.secret_key = "tajni_kljuc"

# ROLA
def rola():
   if ulogovan():
       return ast.literal_eval(session["ulogovani_korisnik"]).pop("rola")

# ULOGOVAN
def ulogovan():
    if "ulogovani_korisnik" in session:
        return True
    else:
        return False


#? RUTE***************************************************

#? EXPORTOVANJE------------
@app.route("/export/<tip>")
def export(tip):
    switch = {
        "studenti": "SELECT * FROM studenti",
        "korisnici": "SELECT * FROM korisnici",
        "predmeti": "SELECT * FROM predmeti",
    }
    upit = switch.get(tip)

    kursor.execute(upit)

    rezultat = kursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    for row in rezultat:
        red = []
        for value in row.values():
            red.append(str(value))
            writer.writerow(red)
    output.seek(0)

    return Response(
        output,
        mimetype = "text/csv",
        headers = {"Content-Disposition": "attachment;filename=" + tip + ".csv"},
    )


#? LOGOVANJE--------------------------------
@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    elif request.method == 'POST':
        forma = request.form
        
        upit = "SELECT * FROM korisnici WHERE email=%s"
        vrednost = (forma["email"],)
        
        kursor.execute(upit, vrednost)
        korisnik = kursor.fetchone()
        if korisnik:
            if check_password_hash(korisnik["lozinka"], forma["lozinka"]):
                # upisivanje korisnika u sesiju
                session["ulogovani_korisnik"] = str(korisnik) 
                return redirect(url_for("studenti"))
            else:
                pymsgbox.alert('Pogresna lozinka!', 'Greska')
                return render_template("login.html")
        else:
            pymsgbox.alert('Pogresna email adresa!', 'Greska')

            return render_template("login.html")
 
@app.route("/logout", methods=['GET'])
def logout():
    session.pop("ulogovani_korisnik", None)
    return redirect(url_for("login"))


#? KORISNICI-----------------------------
@app.route("/korisnici", methods=['GET'])
def korisnici():
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        upit = "SELECT * FROM korisnici"
        kursor.execute(upit)
        korisnici = kursor.fetchall()
        return render_template("korisnici.html", korisnici=korisnici, rola = rola())
    else:
        return redirect(url_for('login'))

@app.route("/korisnik_novi", methods=['GET', 'POST'])
def korisnik_novi():
    if ulogovan():
        if request.method == 'GET':
            return render_template("korisnik_novi.html")
        elif request.method == 'POST':
            forma = request.form 
            hesovana_lozinka = generate_password_hash(forma["lozinka"])
            vrednosti = (
            forma["ime"],
            forma["prezime"],
            forma["email"],
            forma["rola"],
            hesovana_lozinka,
            )

            upit = """ INSERT INTO 
                korisnici(ime,prezime,email,rola,lozinka)
                VALUES (%s, %s, %s, %s, %s)    
            """
            kursor.execute(upit, vrednosti)
            konekcija.commit()
            send_email(forma["ime"], forma["prezime"], forma["email"], forma["lozinka"])
            return redirect(url_for("korisnici"))
    else:
        return redirect(url_for('login'))

@app.route("/korisnik_izmena/<id>", methods=['GET', 'POST'])
def korisnik_izmena(id):
    if ulogovan():
        if request.method == 'GET':
            upit = "SELECT * FROM korisnici WHERE id=%s"
            vrednost = (id,)
            kursor.execute(upit, vrednost)
            korisnik = kursor.fetchone()

            return render_template("korisnik_izmena.html", korisnik=korisnik, rola = rola())
        elif request.method == 'POST':
            forma = request.form
            hashovana_lozinka = generate_password_hash(forma["lozinka"])

            vrednosti = (
            forma["ime"], 
            forma["prezime"], 
            forma["email"], 
            hashovana_lozinka, 
            id, 
            )

            upit = """UPDATE korisnici SET 
            ime=%s, 
            prezime=%s, 
            email=%s, 
            lozinka=%s 
            WHERE id=%s
            """
            kursor.execute(upit, vrednosti) 
            konekcija.commit()

            return redirect(url_for("korisnici"))
    else:
        return redirect(url_for('login'))

@app.route("/korisnik_brisanje/<id>", methods=['GET','POST'])
def korisnik_brisanje(id):
    if ulogovan():
        upit = "DELETE FROM korisnici WHERE id=%s"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        konekcija.commit()
        return redirect(url_for("korisnici"))
    else:
        return redirect(url_for('login'))


#? PREDMETI-----------------------------
@app.route("/predmeti", methods=['GET'])
def predmeti():
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        upit = "SELECT * FROM predmeti"
        kursor.execute(upit)
        predmeti = kursor.fetchall()

        return render_template("predmeti.html", predmeti=predmeti, rola = rola())
    else:
        return redirect(url_for('login'))

@app.route("/predmet_novi", methods=['GET','POST'])
def predmet_novi():
    if ulogovan():
        if request.method == 'GET':
            return render_template("predmet_novi.html")
        elif request.method == 'POST':
            forma = request.form 
            vrednosti = (
            forma["sifra"],
            forma["naziv"],
            forma["godina"],
            forma["espb"],
            forma["o/i"],
            )

            upit = """ INSERT INTO 
                predmeti(sifra,naziv,godina_studija,espb,obavezni_izborni)
                VALUES (%s, %s, %s, %s, %s)    
            """
            kursor.execute(upit, vrednosti)
            konekcija.commit()
            return redirect(url_for("predmeti"))
    else:
        return redirect(url_for('login'))

@app.route("/predmet_izmena/<id>", methods=['GET', 'POST'])
def predmeti_izmena(id):
    if ulogovan():
        if request.method == 'GET':
            upit = "SELECT * FROM predmeti WHERE id=%s"
            vrednost = (id,)
            kursor.execute(upit, vrednost)
            predmeti = kursor.fetchone()

            return render_template("predmet_izmena.html", predmeti=predmeti, rola = rola())
        elif request.method == 'POST':
            forma = request.form
            
            vrednosti = (
            forma['sifra'],
            forma["naziv"],
            forma["godina_studija"],
            forma["espb"],
            # forma['obavezni_izborni'],
            id,
            )

            upit = """UPDATE predmeti SET 
            sifra=%s, 
            naziv=%s, 
            godina_studija=%s, 
            espb=%s
            # o/i=%s 
            WHERE id=%s
            """
            kursor.execute(upit, vrednosti)
            konekcija.commit()

            return redirect(url_for("predmeti"))
    else:
        return redirect(url_for('login'))

@app.route("/predmet_brisanje/<id>", methods=['GET'])
def predmeti_brisanje(id):
    if ulogovan():
        upit = "DELETE FROM predmeti WHERE id=%s"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        konekcija.commit()

        return redirect(url_for("predmeti"))
    else:
        return redirect(url_for('login'))

#? STUDENTI-----------------------------
@app.route("/studenti", methods=['GET'])
def studenti():
    if ulogovan():
        upit = "SELECT * FROM studenti"
        kursor.execute(upit)
        studenti = kursor.fetchall()

        return render_template("studenti.html", studenti=studenti, rola=rola())
    else:
        return redirect(url_for('login'))

@app.route("/student/<id>", methods=['GET','POST'])
def student(id):
    if ulogovan():
        upit = "SELECT * FROM studenti WHERE id=%s"
        vrednost = (id,)
        kursor.execute(upit,vrednost)
        student = kursor.fetchone()

        upit = "SELECT * FROM predmeti"
        kursor.execute(upit)
        predmeti = kursor.fetchall()

        upit = "SELECT predmeti.sifra, predmeti.naziv, predmeti.godina_studija, predmeti.obavezni_izborni, predmeti.espb, ocene.ocena, ocene.id FROM ocene JOIN predmeti ON ocene.predmet_id=predmeti.id WHERE sudent_id=%s"
        vredntost = (id,)
        kursor.execute(upit,vredntost)
        ocene = kursor.fetchall()
        return render_template("student.html", student = student, predmeti = predmeti, ocene = ocene, rola = rola())
    else:
        return redirect(url_for('login'))

@app.route("/student_novi", methods=['GET','POST'])
def student_novi():
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        if request.method == 'GET':
            return render_template("student_novi.html")
        elif request.method == 'POST':
            forma = request.form 
            
            vrednosti = (
            forma["ime"],
            forma["ime_roditelja"],
            forma["prezime"],
            forma["broj_indeksa"],
            forma["godina_studija"],
            forma["jmbg"],
            forma["datum_rodjenja"],
            forma["broj_telefona"],
            forma["email"],
            "0",
            "0",
            )

            upit = """ INSERT INTO 
                studenti(ime,ime_roditelja,prezime,broj_indeksa,godina_studija,jmbg,datum_rodjenja,broj_telefona,email,prosek_ocena,espb)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)    
            """
            kursor.execute(upit, vrednosti)
            konekcija.commit()
            return redirect(url_for("studenti"))
    else:
        return redirect(url_for('login'))

@app.route("/student_izmena/<id>", methods=['GET', 'POST'])
def student_izmena(id):
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        if request.method == 'GET':
            upit = "SELECT * FROM studenti WHERE id=%s"
            vrednost = (id,)
            kursor.execute(upit, vrednost)
            studenti = kursor.fetchone()

            return render_template("student_izmena.html", studenti=studenti, rola = rola())
        elif request.method == 'POST':
            forma = request.form
            
            vrednosti = (
            forma['broj_indeksa'],
            forma["ime"],
            forma["ime_roditelja"],
            forma["prezime"],
            forma["e-mail"],
            forma["broj_telefona"],
            forma["godina_studija"],
            forma["datum"],
            forma["jmbg"],
            id,
            )

            upit = """UPDATE studenti SET 
            broj_indeksa=%s, 
            ime=%s,
            ime_roditelja=%s,
            prezime=%s,
            e-mail=%s,
            broj_telefona=%s,
            godina_studija=%s,
            datum=%s,
            jmbg=%s,
            WHERE id=%s
            """
            kursor.execute(upit, vrednosti)
            konekcija.commit()

            return redirect(url_for("studenti"))
    else:
        return redirect(url_for('login'))

@app.route("/student_brisanje/<id>", methods=['GET'])
def student_brisanje(id):
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        upit = "DELETE FROM studenti WHERE id=%s"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        konekcija.commit()

        return redirect(url_for("studenti"))
    else:
        return redirect(url_for('login'))


#? OCENE----------------------------------------
@app.route("/ocena_nova/<id>", methods=['POST'])
def ocena_nova(id):
    if ulogovan():
        # Dodavanje ocene u tabelu ocene
        upit = """
            INSERT INTO ocene(sudent_id, predmet_id, ocena, datum)
            VALUES(%s, %s, %s, %s)
            """
        forma = request.form

        vrednosti = (
            id, 
            forma['predmet_id'], 
            forma['ocena'], 
            forma['datum'])

        kursor.execute(upit, vrednosti)
        konekcija.commit()


        # Računanje proseka ocena
        upit = "SELECT AVG(ocena) AS rezultat FROM ocene WHERE sudent_id=%s"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        prosek_ocena = kursor.fetchone()

        # Računanje ukupno espb
        upit = "SELECT SUM(espb) AS rezultat FROM predmeti WHERE id IN (SELECT predmet_id FROM ocene WHERE sudent_id=%s)"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        espb = kursor.fetchone()

        # Izmena tabele student
        upit = "UPDATE studenti SET espb=%s, prosek_ocena=%s WHERE id=%s"
        vrednosti = (espb['rezultat'], prosek_ocena['rezultat'], id)
        kursor.execute(upit, vrednosti)
        konekcija.commit()
        return redirect(url_for('student', id=id))
    else:
        return redirect(url_for('login'))

@app.route("/ocena_izmena/<id>/<ocena_id>", methods=['GET','POST'])
def ocena_izmena(id, ocena_id):
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        if request.method == 'GET':
            
            upit = "SELECT * FROM studenti WHERE id=%s"
            vrednost = (id,)
            kursor.execute(upit,vrednost)
            student = kursor.fetchone()

            upit = "SELECT * FROM predmeti"
            kursor.execute(upit)
            predmeti = kursor.fetchall()

            upit = "SELECT predmeti.sifra, predmeti.naziv, predmeti.godina_studija, predmeti.obavezni_izborni, predmeti.espb, ocene.ocena, ocene.id FROM ocene JOIN predmeti ON ocene.predmet_id=predmeti.id WHERE sudent_id=%s"
            vredntost = (id,)
            kursor.execute(upit,vredntost)
            ocene = kursor.fetchall()

            upit = "SELECT * FROM ocene WHERE id=%s"
            vrednost = (ocena_id,)
            kursor.execute(upit, vrednost)
            data_ocena = kursor.fetchone()

            return render_template("ocena_izmena.html", student = student, predmeti = predmeti, ocene = ocene, data_ocena = data_ocena, id = id)

        elif request.method == 'POST':
            forma = request.form

            vrednosti = (
            forma["predmet_id"],
            forma["ocena"],
            forma["datum"],
            ocena_id,
            )

            upit = """UPDATE ocene SET
            predmet_id=%s,
            ocena=%s,
            datum=%s

            WHERE id=%s
            """
            kursor.execute(upit, vrednosti)

            # Računanje proseka ocena
            upit = "SELECT AVG(ocena) AS rezultat FROM ocene WHERE sudent_id=%s"
            vrednost = (id,)
            kursor.execute(upit, vrednost)
            prosek_ocena = kursor.fetchone()

            # Računanje ukupno espb
            upit = "SELECT SUM(espb) AS rezultat FROM predmeti WHERE id IN (SELECT predmet_id FROM ocene WHERE sudent_id=%s)"
            vrednost = (id,)
            kursor.execute(upit, vrednost)
            espb = kursor.fetchone()

            # Izmena tabele student
            upit = "UPDATE studenti SET espb=%s, prosek_ocena=%s WHERE id=%s"
            vrednosti = (espb['rezultat'], prosek_ocena['rezultat'], id)
            kursor.execute(upit, vrednosti)
            konekcija.commit()
            return redirect(url_for('student', id=id))
        else:
            return redirect(url_for('login'))

@app.route("/ocena_brisanje/<id>/<ocena_id>", methods=['GET', 'POST'])
def ocena_brisanje(id, ocena_id):
    if rola() != "Administrator":
        pymsgbox.alert('Nemate pristup zeljenoj stanici!', 'Upozorenje')
        return redirect(url_for("studenti"))
    elif ulogovan():
        upit = "DELETE FROM ocene WHERE id=%s"

        vrednost = (ocena_id,)
        kursor.execute(upit, vrednost)

        upit = "SELECT AVG(ocena) AS rezultat FROM ocene WHERE sudent_id=%s"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        prosek_ocena = kursor.fetchone()

        # Računanje ukupno espb
        upit = "SELECT SUM(espb) AS rezultat FROM predmeti WHERE id IN (SELECT predmet_id FROM ocene WHERE sudent_id=%s)"
        vrednost = (id,)
        kursor.execute(upit, vrednost)
        espb = kursor.fetchone()

        # Izmena tabele student
        upit = "UPDATE studenti SET espb=%s, prosek_ocena=%s WHERE id=%s"
        vrednosti = (espb['rezultat'], prosek_ocena['rezultat'], id)
        kursor.execute(upit, vrednosti)

        konekcija.commit()
        return redirect(url_for('student', id=id))
    else:
        return redirect(url_for(login))


app.run(debug=True)
 
