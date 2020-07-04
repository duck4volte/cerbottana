import os
from datetime import date

from flask import Flask, render_template, session, abort, request, g
from waitress import serve  # type: ignore

import database
import utils


class Server(Flask):
    def serve_forever(self) -> None:
        serve(self, listen="*:{}".format(os.environ["PORT"]))


SERVER = Server(__name__)

SERVER.secret_key = os.environ["FLASK_SECRET_KEY"]


@SERVER.template_filter("format_date")
def format_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y")


@SERVER.before_request
def before():
    g.db = database.open_db()

    token = request.args.get("token")

    if token is not None:
        sql = "SELECT rank FROM tokens WHERE token = ? AND JULIANDAY() - JULIANDAY(scadenza) < 0"
        rank = g.db.execute(sql, [token]).fetchone()
        if rank:
            session["user"] = rank["rank"]

    if "user" not in session:
        abort(401)


@SERVER.after_request
def after(res):
    db = g.pop("db", None)

    if db is not None:
        db.connection.close()
    return res


@SERVER.route("/", methods=("GET", "POST"))
def dashboard():

    if request.method == "POST":

        if "approva" in request.form:
            parts = request.form["approva"].split(",")
            sql = "UPDATE utenti SET descrizione = descrizione_daapprovare, descrizione_daapprovare = '' "
            sql += " WHERE id = ? AND descrizione_daapprovare = ?"
            g.db.execute(sql, [parts[0], ",".join(parts[1:])])

        if "rifiuta" in request.form:
            parts = request.form["rifiuta"].split(",")
            sql = "UPDATE utenti SET descrizione_daapprovare = '' "
            sql += " WHERE id = ? AND descrizione_daapprovare = ?"
            g.db.execute(sql, [parts[0], ",".join(parts[1:])])

        g.db.connection.commit()

    sql = "SELECT * FROM utenti WHERE descrizione_daapprovare != '' ORDER BY userid"
    descrizioni_daapprovare = g.db.execute(sql).fetchall()

    return render_template(
        "dashboard.html", descrizioni_daapprovare=descrizioni_daapprovare
    )


@SERVER.route("/profilo", methods=("GET", "POST"))
def profilo():

    userid = utils.to_user_id(request.args.get("userid", ""))

    if request.method == "POST":

        if "descrizione" in request.form:
            sql = "UPDATE utenti SET descrizione = ? WHERE id = ? AND userid = ?"
            g.db.execute(sql, [request.form["descrizione"], request.form["id"], userid])

        g.db.connection.commit()

    sql = "SELECT * FROM utenti WHERE userid = ?"
    utente = g.db.execute(sql, [utils.to_user_id(userid)]).fetchone()

    return render_template("profilo.html", utente=utente, today=date.today())


@SERVER.route("/eightball", methods=("GET", "POST"))
def eightball():

    if request.method == "POST":

        if "risposte" in request.form:
            sql = "DELETE FROM eight_ball"
            g.db.execute(sql)

            risposte = list(
                filter(
                    None,
                    map(
                        str.strip, sorted(request.form["risposte"].strip().splitlines())
                    ),
                )
            )
            sql = "INSERT INTO eight_ball (risposta) VALUES " + ", ".join(
                ["(?)"] * len(risposte)
            )
            g.db.execute(sql, risposte)

        g.db.connection.commit()

    sql = "SELECT * FROM eight_ball ORDER BY risposta"
    rs = g.db.execute(sql).fetchall()

    return render_template("eightball.html", rs=rs)
