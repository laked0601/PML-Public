from webserver_app import wsapp
from flask import render_template, request, redirect, jsonify, abort, make_response
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, BooleanField, SelectField, DateField, DecimalField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, Optional, NumberRange, ValidationError
from wtforms.widgets import DateInput
from sqlite_interaction import sql_connection
from globals import MAX_UNSIGNED_INT, DEMO, BASE_ENDPOINT
from errors import not_found
from flask_cors import CORS, cross_origin
from application.backend_api import tickerSearch, get_api_price
import application.accounting as accounting
from datetime import date, timedelta
from time import mktime


class PortfolioForm(FlaskForm):
    number = IntegerField(validators=[DataRequired(), NumberRange(min=0, max=4294967295)])

    def __init__(self, *args, cursor=None, **kwargs):
        super(PortfolioForm, self).__init__(*args, **kwargs)
        self.cursor = cursor

    def validate_number(self, field):
        self.cursor.execute("SELECT EXISTS (SELECT 1 FROM portfolios WHERE PK = ?) AS record_exists;", (field.data,))
        if not self.cursor.fetchone()[0]:
            raise ValidationError("This portfolio does not exist")


class createPorfolioForm(FlaskForm):
    #  You will need to create a flask form for a new portfolio, use the model above
    name = StringField(validators=[InputRequired(), Length(max=100)])
    description = StringField(validators=[InputRequired(), Length(max=500)])


class modifyPortfolioForm(PortfolioForm):
    mod_name = StringField(validators=[InputRequired(), Length(max=100)])
    mod_description = TextAreaField(validators=[InputRequired(), Length(max=500)])

    def __init__(self, *args, cursor=None, **kwargs):
        super(modifyPortfolioForm, self).__init__(*args, cursor=cursor, **kwargs)


@wsapp.route(BASE_ENDPOINT + "/portfolios.html", methods=['GET', 'POST'])
def portfolios():
    with sql_connection() as c:
        cursor = c.cursor()
        form = createPorfolioForm()
        if request.method == "POST":
            if form.validate() and not DEMO:
                accounting.add_portfolio(form.name.data, form.description.data)

        return render_template("portfolios.html", form=form,
                               portfolios=accounting.get_portfolios(connection=c, cursor=cursor),
                               BASE_ENDPOINT=BASE_ENDPOINT,
                               DEMO=DEMO)


@wsapp.route(BASE_ENDPOINT + "/reset-portfolio", methods=['POST'])
def reset_portfolio():
    redirect_url = "/portfolios.html"
    if request.method == "POST":
        with sql_connection() as c:
            cursor = c.cursor()
            form = PortfolioForm(request.form, cursor=cursor)
            if form.validate():
                if not DEMO:
                    cursor.execute("delete from holdings where portfolio = ?", (form.number.data,))
                    c.commit()
                redirect_url = "/holdings.html?number=" + str(form.number.data)
    return redirect(BASE_ENDPOINT + redirect_url)


class addHoldingForm(FlaskForm):
    portfolio = IntegerField(validators=[DataRequired(), NumberRange(min=1, max=MAX_UNSIGNED_INT)])
    ticker = StringField(validators=[DataRequired(), Length(max=50)])


@wsapp.route(BASE_ENDPOINT + "/add_holding", methods=["POST"])
def add_holding():
    form = addHoldingForm(request.form)
    if form.validate():
        with sql_connection() as c:
            if not DEMO:
                cursor = c.cursor()
                accounting.add_holding(form.ticker.data, form.portfolio.data, cursor=cursor, connection=c)
            return redirect(BASE_ENDPOINT + "/holdings.html?number=" + str(form.portfolio.data))
    return jsonify(form.errors)


@wsapp.route(BASE_ENDPOINT + "/delete-portfolio", methods=["POST"])
def delete_portfolio():
    with sql_connection() as c:
        cursor = c.cursor()
        form = PortfolioForm(request.form, cursor=cursor)
        if form.validate() and not DEMO:
            cursor.execute("delete from portfolios where PK = ?", (form.number.data,))
            c.commit()
    return make_response("200")


@wsapp.route(BASE_ENDPOINT + "/holdings.html", methods=["GET", "POST"])
@cross_origin()
def holdings():
    with sql_connection() as c:
        cursor = c.cursor()
        if request.method == "GET":
            form = PortfolioForm(request.args, cursor=cursor, meta={'csrf': False})
            if form.validate():
                hlds = accounting.get_holdings(form.number.data, connection=c, cursor=cursor)
                cursor.execute("select * from portfolios_expanded where PK = ?", (form.number.data,))
                add_form = addHoldingForm()
                add_form.portfolio.data = form.number.data
                reset_portfolio_form = PortfolioForm()
                reset_portfolio_form.number.data = form.number.data

                pf = accounting.Portfolio(
                    **{x[0]: x[1] for x in zip([x[0] for x in cursor.description], cursor.fetchone())}
                )

                mod_portfolio = modifyPortfolioForm()
                mod_portfolio.number.data = pf.PK
                mod_portfolio.mod_name.data = pf.name
                mod_portfolio.mod_description.data = pf.description

                template_content = render_template(
                    "portfolio_edit.html",
                    portfolio=pf,
                    mod_portfolio_form=mod_portfolio,
                    holdings=hlds,
                    add_holding=add_form,
                    reset_portfolio=reset_portfolio_form,
                    BASE_ENDPOINT=BASE_ENDPOINT
                )

                # Create a response using make_response
                response = make_response(template_content)

                # Set headers
                response.headers['Content-Type'] = 'text/html'
                response.headers['Access-Control-Allow-Origin'] = 'danl.info'
                return template_content
        elif request.method == "POST":
            form = modifyPortfolioForm(request.form, cursor=cursor)
            if form.validate():
                if not DEMO:
                    cursor.execute("update portfolios set name = ?, description = ? where PK = ?",
                                   (form.mod_name.data, form.mod_description.data, form.number.data))
                    c.commit()
                return redirect(BASE_ENDPOINT + f"/holdings.html?number={form.number.data}")
    return not_found()


class holdingForm(FlaskForm):
    portfolio = IntegerField('Portfolio', validators=[InputRequired(), NumberRange(min=1, max=4294967295)])
    holding = IntegerField('Holding', validators=[InputRequired(), NumberRange(min=1, max=4294967295)])

    def __init__(self, *args, cursor=None, **kwargs):
        super(holdingForm, self).__init__(*args, **kwargs)
        self.cursor = cursor

    def validate_holding(self, field):
        self.cursor.execute("SELECT PK FROM holdings WHERE PK = ? and portfolio = ?",
                            (field.data, self.portfolio.data))
        if self.cursor.fetchone() is None:
            raise ValidationError('Invalid holding number')


class postHoldingForm(holdingForm):
    action = SelectField("Action", choices=[("Buy", "Buy"), ("Sell", "Sell")], validators=[Optional()])
    units = IntegerField("Units", validators=[Optional(), NumberRange(min=1, max=4294967295)])
    amount = DecimalField('Amount', places=2, validators=[DataRequired(), NumberRange(min=0, max=4294967295)])
    trade_date = DateField("Trade Date", validators=[InputRequired()], widget=DateInput())

    def __init__(self, *args, **kwargs):
        super(postHoldingForm, self).__init__(*args, **kwargs)
        today = date.today()
        two_years_ago = today - timedelta(days=365 * 2)
        self.trade_date.default = today
        self.trade_date.min = two_years_ago
        self.trade_date.max = today

    def validate_action(self, field):
        if self.units.data is None or self.units.data == 0:
            raise ValidationError("Cannot perform a trade action without units")
        if field.data == "Sell":
            self.cursor.execute("select sum(units) >= ? from trades where portfolio_holding = ? and trade_date = ?",
                                (self.units.data, self.holding.data, mktime(self.trade_date.data.timetuple())))
            if self.cursor.fetchone()[0] != 1:
                raise ValidationError("Cannot sell more than the total units at this date")

    def validate_amount(self, field):
        if field.data is None:
            raise ValidationError("Cannot trade with null amount")
        self.amount.data = float(field.data)


@wsapp.route(BASE_ENDPOINT + "/modify-holding.html", methods=["GET", "POST"])
def modify_holding():
    with sql_connection() as c:
        cursor = c.cursor()
        holding_pk = None
        post_form = postHoldingForm()
        message = ""
        if request.method == "GET":
            form = holdingForm(request.args, cursor=cursor, meta={"csrf": False})
            if form.validate():
                holding_pk = form.holding.data
        elif request.method == "POST":
            form = postHoldingForm(request.form, cursor=cursor)
            if form.validate():
                if not DEMO:
                    # process transaction
                    accounting.trade(PK=form.holding.data, units=form.units.data, amount=form.amount.data,
                                     trade_date=form.trade_date.data, transaction_type=form.action.data,
                                     connection=c, cursor=cursor)
                    message = "Traded %d units successfuly!" % (form.units.data,)
                    form.units.data = ""
                    form.amount.data = ""
                holding_pk = form.holding.data
            else:
                if "action" in form.errors:
                    message = form.errors["action"][0]
                form = holdingForm(request.form, cursor=cursor)
                if form.validate():
                    holding_pk = form.holding.data

        if holding_pk is not None:
            holding = accounting.get_holding(holding_number=holding_pk, connection=c, cursor=cursor)
            post_form.portfolio.data = form.portfolio.data
            post_form.holding.data = form.holding.data
            cursor.execute("SELECT strftime('%d/%m/%Y', datetime(tr.trade_date, 'unixepoch')) AS trade_date, tr.type, "
                           "sec.ticker, tr.units, tr.amount FROM trades tr "
                           "LEFT JOIN holdings hld ON tr.portfolio_holding = hld.PK "
                           "LEFT JOIN securities sec ON hld.security = sec.PK "
                           "WHERE tr.portfolio_holding = ? ORDER BY tr.trade_date, tr.PK DESC;",
                           (form.holding.data,))
            return render_template("modify_holding.html", security=holding, form=post_form, message=message,
                                   trades=cursor.fetchall(), BASE_ENDPOINT=BASE_ENDPOINT)
        return not_found()


class priceForm(FlaskForm):
    PK = IntegerField('PK', validators=[InputRequired(), NumberRange(min=1, max=4294967295)])
    date = DateField('Date', validators=[InputRequired()], format="%Y-%m-%d")

    def __init__(self, *args, cursor=None, **kwargs):
        super(priceForm, self).__init__(*args, **kwargs)
        self.cursor = cursor
        self.ticker = None

    def validate_PK(self, field):
        self.cursor.execute("select ticker FROM securities WHERE PK = ?", (field.data,))
        res = self.cursor.fetchone()
        if res is None:
            raise ValidationError('Invalid security number')
        self.ticker = res[0]

    def validate_date(self, field):
        if field.data is not None:
            today = date.today()
            if today - timedelta(days=365 * 20) <= field.data <= today:
                return True
        raise ValidationError("Invalid date")


@wsapp.route(BASE_ENDPOINT + "/get-price", methods=["GET"])
def get_price():
    if request.method == "GET":
        with sql_connection() as c:
            cursor = c.cursor()
            form = priceForm(request.args, cursor=cursor, meta={"csrf": False})
            if not form.validate():
                resp = make_response(jsonify(form.errors), 400)
                return resp
            date_timestamp = mktime(form.date.data.timetuple())
            cursor.execute("select px.price, px.date from prices px "
                           "left join securities sec on px.security = sec.PK "
                           "where px.security = ? and px.date between ? - 86400 * 4 and ? order by px.date desc",
                           (form.PK.data, date_timestamp, date_timestamp))
            res = cursor.fetchone()
            if res is None:
                res = get_api_price(form.ticker, form.date.data)
                if res is not None:
                    price = res[1]
                    date_str = res[0]
                    date_timestamp = mktime(date.fromisoformat(date_str).timetuple())
                    cursor.execute("INSERT OR IGNORE INTO prices (security, date, price) VALUES (?, ?, ?)",
                                   (form.PK.data, date_timestamp, price))
                    c.commit()
                else:
                    resp = make_response(jsonify({"errors": "No price exists at this date"}), 400)
                    return resp
            else:
                price = res[0]
                date_str = date.fromtimestamp(res[1]).isoformat()
            return jsonify({"price": price, "date": date_str})


def get_holdings_count(portfolio_number, cursor):
    cursor.execute("SELECT count(*) FROM portfolio_holdings WHERE portfolio = ?;", (portfolio_number, ))
    row = cursor.fetchone()
    return row[0]
