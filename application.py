from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    # select symbol and amount owned by user
    port = db.execute("SELECT symbol, amount FROM portfolio WHERE id = :id", id=session["user_id"])

    total_value = 0

    for port in port:
        symbol = port["symbol"]
        amount = port["amount"]
        stock = lookup(symbol)
        value = stock["price"] * amount
        total_value = total_value + value
        db.execute("UPDATE portfolio SET price = :price, value = :value WHERE id= :id AND symbol= :symbol", price = stock["price"], value = value, id = session["user_id"], symbol = symbol)

    # find cash in users table
    cash = db.execute("SELECT cash FROM users WHERE id =:id", id=session["user_id"] )

    # find grand total
    grand_total = total_value + cash[0]["cash"]

    # print portflio
    print_port = db.execute("SELECT * FROM portfolio WHERE id = :id", id=session["user_id"])

    return render_template("index.html", stocks =print_port, cash= cash[0]["cash"], grand_total= grand_total )

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """deposit cash in account."""

    if request.method == "GET":
        return render_template("cash.html")
    else:
        deposit = int(request.form.get("deposit"))

        #make sure the amount is a positive interger
        if deposit < 0:
                return apology("must provide valid cash deposit")

        else:
            #update the cash in the users table
            db.execute("UPDATE users SET cash = cash+:deposit WHERE id = :id",  deposit = deposit, id = session["user_id"])
            cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
            return render_template("cashed.html", cashed = cash[0]["cash"])

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    if request.method == "GET":
        return render_template("buy.html")
    else:
            #get the information on the stock from yahoo using the lookup function
            rows = lookup(request.form.get("stock_symbol"))
            amount = int(request.form.get("stock_amount"))

            #ensure symbol is valid
            if rows == None:
                return apology("must provide valid symbol")
            #make sure the amount is a positive interger
            elif amount < 0:
                return apology("must provide valid amount of shares")

            else:
                #check if there is enough money on the users account
                money = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
                if not money or float(money[0]["cash"]) < (rows["price"]*amount):
                    return apology("not enough money in your account")

                #update the history database
                else:
                    db.execute("INSERT INTO history (symbol, amount, price, id) VALUES(:symbol, :amount, :price, :id)", \
                        symbol=rows["symbol"], amount=amount, price =rows["price"], id =session["user_id"])
                    #update the cash in the users table
                    db.execute("UPDATE users SET cash = :cash WHERE id = :id",  cash = float(money[0]["cash"]) - (rows["price"]*float(amount)), id = session["user_id"])

                    # find stock in portfolio
                    user_port = db.execute("SELECT amount FROM portfolio WHERE id = :id AND symbol = :symbol", id = session["user_id"], symbol = rows["symbol"])

                    #if the share is not owned yet add it
                    if not user_port :
                        db.execute("INSERT INTO portfolio (symbol, amount, id) VALUES (:symbol, :amount, :id)", symbol = rows["symbol"], amount = amount, id = session["user_id"])

                    # if shares is owned yet ncrement the amount
                    else:
                        amount_new = int(user_port[0]["amount"]) +amount
                        db.execute("UPDATE portfolio SET amount =:amount WHERE id = :id AND symbol = :symbol", amount = amount_new, id = session["user_id"], symbol = rows["symbol"])

            return redirect(url_for("index"))

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    history = db.execute("SELECT * from history WHERE id=:id", id= session["user_id"])

    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        #get the information on the stock from yahoo using the lookup function
        rows = lookup(request.form.get("stock_symbol"))

        #ensure symbol is valid
        if rows == None:
            return apology("must provide valid symbol")

        else:
            return render_template("quoted.html", stock = rows)

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # ensure password was confirmed
        elif request.form.get("password_conf") != request.form.get("password"):
            return apology("must confirm password")

        # encrypt the password
        hash = pwd_context.hash(request.form.get("password"))

        # query to add user to database
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash = hash)
        if not result:
            return apology("username already in use")

        # remember which user has logged in
        session["user_id"] = result

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    if request.method == "GET":
        return render_template("sell.html")
    else:
            #get the information on the stock from yahoo using the lookup function
            rows = lookup(request.form.get("stock_symbol"))
            sell_amount = int(request.form.get("stock_amount"))

            #ensure symbol is valid
            if rows == None:
                return apology("must provide valid symbol")
            #make sure the amount is a positive interger
            elif sell_amount < 0:
                return apology("must provide valid amount of shares")

            else:
                #check if the user has this stock
                port = db.execute("SELECT amount FROM portfolio WHERE id = :id AND symbol = :symbol", id = session["user_id"], symbol = rows["symbol"])
                if not port or float(port[0]["amount"]) < sell_amount:
                    return apology("NOt enough of this stock in your portfolio")

                else:
                    #update the history database
                    db.execute("INSERT INTO history (symbol, amount, price, id) VALUES(:symbol, :amount, :price, :id)", \
                        symbol=rows["symbol"], amount=- sell_amount, price =rows["price"], id =session["user_id"])

                    #update the cash in the users table
                    money = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
                    db.execute("UPDATE users SET cash= cash+ :new WHERE id = :id",  new = rows["price"]*float(sell_amount), id = session["user_id"])

                    #if all shares are sold delete stock from portfolio
                    if port[0]["amount"]-sell_amount == 0 :
                        db.execute("DELETE FROM portfolio WHERE id = :id AND symbol = :symbol", id = session["user_id"], symbol = rows["symbol"])

                    # if there are shares left after the sell update the portfolio
                    else:
                        amount_new = int(port[0]["amount"]) - sell_amount
                        db.execute("UPDATE portfolio SET amount =:amount WHERE id = :id AND symbol = :symbol", amount = amount_new, id = session["user_id"], symbol = rows["symbol"])

            return redirect(url_for("index"))