import os

import sqlite3
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup
from datetime import datetime

ID = 0
USERNAME = 1
HASH = 2
CASH = 3

SYMBOL = 0
SHARES = 1
PRICE = 2
TRANSACTED = 3
USERID = 4

# api key
# export API_KEY=pk_0fb799a879ef4f5fbe4e721f4f8afe04

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

connection = sqlite3.connect("finance.db", check_same_thread=False)
db = connection.cursor()
db.execute("""CREATE TABLE IF NOT EXISTS'users' ('id' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 'username' TEXT NOT NULL, 'hash' TEXT NOT NULL, 'cash' NUMERIC NOT NULL DEFAULT 10000.00 )""")


db.execute("""CREATE TABLE IF NOT EXISTS'stocks' ('symbol' varchar(255) NOT NULL, 'shares' integer NOT NULL, 'price' real NOT NULL, 'transacted' datetime NOT NULL, 'userid' integer NOT NULL) """)

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # everything with that user
    db.execute("SELECT symbol, SUM(shares) FROM stocks WHERE userid=? GROUP BY symbol", (session['user_id'],))
    rows = db.fetchall()
    rows = list(rows)

    total = 0

    printRows = []

    for row in rows:
        response = lookup(row[0])
        oneRow = {}
        oneRow["symbol"] = row[0]
        oneRow["price"] = response["price"]
        oneRow["name"] = response["name"]
        oneRow["SUM(shares)"] = row[1]
        oneRow["total"] = oneRow["price"] * row[1]
        printRows.append(oneRow)
        total += oneRow["total"]

    db.execute("SELECT cash FROM users WHERE id=?", ((session['user_id']),))
    cash = db.fetchall()
    cash = cash[0][0]
    total += cash

    return render_template("index.html", rows=printRows, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        response = lookup(symbol)

        # if response is null
        if (not response):
            return apology("invalid symbol")
        # if number is not positive
        elif (shares < 0):
            return apology("invalid shares")

        # need to check if they have enough cash
        # price of stock and how much cash current user has
        price = response["price"]
        db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
        cash = db.fetchall()
        cash = cash[0][CASH]

        # cannot afford
        if (price * shares > cash):
            return apology("not enough cash")
        # can afford, will buy
        db.execute("UPDATE users SET cash=? WHERE id=?", (cash - price * shares, session["user_id"],))
        db.execute("INSERT INTO stocks VALUES(?, ?, ?, ?, ?)", (symbol, shares, price, datetime.now(), session['user_id'],))

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    db.execute("SELECT symbol, shares, price, transacted FROM stocks WHERE userid=?", (session["user_id"],))
    rows = db.fetchall()

    printRows = []

    for row in rows:
        response = lookup(row[0])
        oneRow = {}
        print(response)
        oneRow["symbol"] = row[0]
        oneRow["shares"] = row[1]
        oneRow["price"] = row[2]
        oneRow["transacted"] = row[3]
        printRows.append(oneRow)

    return render_template("history.html", rows=printRows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        db.execute("SELECT * FROM users WHERE username = ?",
                          (request.form.get("username"),))
        rows = db.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][HASH], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0][ID]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        response = lookup(symbol)

        if (not response):
            return apology("Invalid Symbol")
        else:
            return render_template("quoted.html", name=response["name"], price=response["price"], symbol=response["symbol"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user id
    session.clear()

    # if post (submitting):
    if request.method == "POST":

        # let rows be the array of users whos username is the one entered
        db.execute("SELECT * FROM users WHERE username = ?", 
        (request.form.get("username"),))
        rows = db.fetchall()

        #if username is empty
        if (not request.form.get("username")):
            return apology("must enter a username", 403)
        # if username already exists in the database
        elif (len(rows) != 0):
            return apology("username already exists", 403)
        # if password field is empty
        elif (not request.form.get("password")):
            return apology("must enter a password", 403)
        # if confirm password field is empty
        elif (not request.form.get("confirmation")):
            return apology("must enter a confirmation password", 403)
        # if passwords do not match
        elif(request.form.get("password") != request.form.get("confirmation")):
            return apology("passwords do not match", 403)
        # if the user everything is FINE
        else:
            # Remember which user has logged in
            session["user_id"] = request.form.get('username')

            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (request.form.get("username"), generate_password_hash(request.form.get("password"),)))

            # Redirect user to home page
            return redirect("/login")
    # if user is loading up the register page
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    db.execute("SELECT symbol, SUM(shares) FROM stocks WHERE userid=? GROUP BY symbol", (session['user_id'],))
    rows = db.fetchall()

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # find the amount currently owned for symbol
        for row in rows:
            if row[0] == symbol:
                shares_have = int(row[1])
                break

        # if selected more shares than currently owned
        if shares > shares_have:
            apology("too many shares")
        else:
            price = lookup(symbol)
            price = price["price"]
            db.execute("SELECT cash FROM users WHERE id=?", (session["user_id"],))
            cash = db.fetchall()
            cash = float(cash[0][0])
            db.execute("INSERT INTO stocks VALUES(?, ?, ?, ?, ?)", (symbol, shares * -1, price, datetime.now(), session['user_id'],))
            db.execute("UPDATE users SET cash=? WHERE id=?", (cash + price * shares, session["user_id"],))
            return redirect("/")
    else:
        symbols = []
        for row in rows:
            symbols.append(row[0])
        return render_template("sell.html", symbols=symbols)

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addCash():
    if request.method == "POST":
        newcash = float(request.form.get("cash"))
        db.execute("SELECT cash FROM users WHERE id=?", ((session['user_id']),))
        oldcash = db.fetchall()
        oldcash = oldcash[0][0]
        # add to database
        totalcash = newcash + oldcash
        db.execute("UPDATE users SET cash=? WHERE id=?", (totalcash, session["user_id"],))
        return redirect("/")
    else:
        return render_template("addcash.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
