from sqlite_interaction import sql_connection
from sqlite3 import Connection, Cursor
from time import time, mktime
from datetime import date
from application.backend_api import tickerSearch, Ticker


REFRESH_CACHE_TIME = 60 * 60 * 24  # set to 60 * 60 * 24 in prod


def _handler_function(fn, **kwargs):
    if "connection" in kwargs and isinstance(kwargs["connection"], Connection):
        if "cursor" in kwargs and isinstance(kwargs["cursor"], Cursor):
            return fn(**kwargs)
        cursor = kwargs["connection"].cursor()
        return fn(cursor=cursor, **kwargs)
    with sql_connection() as connection:
        cursor = connection.cursor()
        return fn(connection=connection, cursor=cursor, **kwargs)


def _trade(PK, units, amount, transaction_type, trade_date, connection, cursor):
    cursor.execute("insert into trades (portfolio_holding, type, units, amount, trade_date) values (?, ?, ?, ?, ?)",
                   (PK, transaction_type, units, amount, mktime(trade_date.timetuple())))
    cursor.execute("update holdings set units = units + ?, cost = ? where PK = ?",
                   (units if transaction_type == "Buy" else -units, _get_weighted_average_cost(PK, cursor),
                    PK))
    connection.commit()


def _get_weighted_average_cost(holding, cursor):
    total_units = 0
    total_cost = 0.0
    wac_per_unit = 0.0
    cursor.execute("select type, units, amount from trades where portfolio_holding = ? order by trade_date asc",
                   (holding,))
    rows = cursor.fetchmany(1000)
    while len(rows) != 0:
        for (ty, units, amount) in rows:
            if ty == "Buy":
                total_units += units
                total_cost = round(total_cost + amount, 2)
            elif ty == "Sell":
                wac_per_unit = total_cost / total_units
                total_units -= units
                total_cost = round(total_units * wac_per_unit, 2)
        rows = cursor.fetchmany(1000)
    return total_cost


def trade(PK, units, amount, transaction_type, trade_date, **kwargs):
    return _handler_function(fn=_trade, PK=PK, units=units, amount=amount, trade_date=trade_date,
                             transaction_type=transaction_type, **kwargs)


def cache_timestamp_valid(last_cache):
    return last_cache > int(time()) - REFRESH_CACHE_TIME


def _check_cache(ticker, connection, cursor):
    cursor.execute("select last_cache_date from securities where ticker = ?", (ticker,))
    res = cursor.fetchone()
    if res is None:
        raise ValueError(f"Ticker '{ticker}' does not exist in SQLite securities")
    if not cache_timestamp_valid(res[0]):
        res = tickerSearch(ticker)
        if res.result_count() != 1:
            raise ValueError(f"Ticker '{ticker}' returned {res.result_count()} results from api")
        res = res.first_result()
        _update_security(ticker, res.name, res.description, res.last_close_price, res.last_price_date,
                         res.share_class_shares_outstanding, res.weighted_shares_outstanding,
                         res.round_lot, res.active, res.homepage_url, res.logo_url, res.icon_url,
                         res.market_cap, res.primary_exchange, res.type, res.sic_code, res.market,
                         connection, cursor)


def check_cache(ticker, **kwargs):
    return _handler_function(fn=_check_cache, ticker=ticker, **kwargs)


def _update_security(ticker, name, description, last_price, last_price_date, share_class_shares_outstanding,
                     weighted_shares_outstanding, round_lot, active, homepage_url, logo_url, icon_url, market_cap,
                     primary_exchange, type, sic_code, market, connection, cursor):
    cursor.execute("UPDATE securities SET name=?, description=?, last_price=?, last_price_date=?, "
                   "share_class_shares_outstanding=?, weighted_shares_outstanding=?, round_lot=?, active=?, "
                   "homepage_url=?, logo_url=?, icon_url=?, market_cap=?, primary_exchange=?, type=?, sic_code=?, "
                   "market=? WHERE ticker=?;",
                   (name, description, last_price, mktime(date.fromisoformat(last_price_date).timetuple()),
                    share_class_shares_outstanding, weighted_shares_outstanding, round_lot, active,
                    homepage_url, logo_url, icon_url, market_cap, primary_exchange, type, sic_code,
                    market, ticker))
    connection.commit()


def update_security(ticker, name, description, last_price, last_price_date, share_class_shares_outstanding,
                     weighted_shares_outstanding, round_lot, active, homepage_url, logo_url, icon_url, market_cap,
                     primary_exchange, type, sic_code, market, last_close_price, **kwargs):
    return _handler_function(fn=_update_security, ticker=ticker, name=name, description=description,
                             last_price=last_price, last_price_date=last_price_date,
                             share_class_shares_outstanding=share_class_shares_outstanding,
                             weighted_shares_outstanding=weighted_shares_outstanding,
                             round_lot=round_lot, active=active, homepage_url=homepage_url,
                             logo_url=logo_url, icon_url=icon_url, market_cap=market_cap,
                             primary_exchange=primary_exchange, type=type, sic_code=sic_code,
                             market=market, last_close_price=last_close_price, **kwargs)


def _get_holdings(portfolio_number, connection, cursor):
    cursor.execute("select ticker from holdings_expanded where portfolio = ?", (portfolio_number,))
    for (ticker_string,) in cursor.fetchall():
        _check_cache(ticker=ticker_string, connection=connection, cursor=cursor)

    cursor.execute("select * from holdings_expanded where portfolio = ?", (portfolio_number,))
    # print(cursor.description)
    return [
        Ticker(**{x[0]: y[i] for i, x in enumerate(cursor.description)})
        for y in cursor.fetchall()
    ]


def get_holdings(portfolio_number, **kwargs):
    return _handler_function(fn=_get_holdings, portfolio_number=portfolio_number, **kwargs)


def _get_holding(holding_number, connection, cursor):
    cursor.execute("select ticker from holdings_expanded where PK = ?", (holding_number,))
    res = cursor.fetchone()
    if res is None:
        raise ValueError(f"Holding could not be found in portfolio holdings {holding_number}")
    _check_cache(ticker=res[0], connection=connection, cursor=cursor)
    cursor.execute("select * from holdings_expanded where PK = ?", (holding_number,))
    return Ticker(**{x[0]: x[1] for x in zip([x[0] for x in cursor.description], cursor.fetchone())})


def get_holding(holding_number, **kwargs):
    return _handler_function(_get_holding, holding_number=holding_number, **kwargs)


class Portfolio:
    def __init__(self, **kwargs):
        self.PK = None
        self.name = None
        self.description = None
        self.holdings_count = None
        self.create_date = None
        self.total_cost = None
        self.total_market_value = None
        self.total_unrealised_gl = None
        self.first_trade_date = None
        for k, v in kwargs.items():
            setattr(self, k, v)


def _get_portfolios(connection, cursor):
    cursor.execute("select * from portfolios_expanded")
    return [
        Portfolio(**{x[0]: y[i] for i, x in enumerate(cursor.description)})
        for y in cursor.fetchall()
    ]


def get_portfolios(**kwargs):
    return _handler_function(fn=_get_portfolios, **kwargs)


def _get_portfolio(PK, connection, cursor):
    cursor.execute("select * from portfolios_expanded where PK = ?", (PK,))
    return Portfolio(**{x[0]: x[1] for x in zip([x[0] for x in cursor.description], cursor.fetchone())})


def get_portfolio(PK, **kwargs):
    return _handler_function(fn=_get_portfolio, PK=PK, **kwargs)


def add_holding(ticker, portfolio_number, cursor, connection):
    cursor.execute("select PK from securities where ticker = ?", (ticker,))
    res = cursor.fetchone()
    if res is None:
        res = tickerSearch(ticker,)
        if res.result_count() == 1:
            new_ticker = res.first_result()
            cursor.execute("insert into securities (ticker, name, description, last_price, last_price_date) "
                           "values (?, ?, ?, ?, ?)",
                           (new_ticker.ticker, new_ticker.name, new_ticker.description,
                            new_ticker.last_close_price,
                            mktime(date.fromisoformat(new_ticker.last_price_date).timetuple())))
            security_pk = cursor.lastrowid
        else:
            raise ValueError(f"No security could be found for ticker '{ticker}'")
    else:
        security_pk = res[0]
    cursor.execute("SELECT "
                   "EXISTS (SELECT 1 FROM holdings WHERE security = ? AND portfolio = ?) as holdings_check, "
                   "EXISTS (SELECT 1 FROM portfolios WHERE PK = ?) as portfolios_check;",
                   (security_pk, portfolio_number, portfolio_number))
    (already_in_portfolio, portfolio_exists) = cursor.fetchone()
    if already_in_portfolio:  # Holding that the user wants to add already exists
        raise ValueError("Holding already exists in portfolio")
    if not portfolio_exists:
        return None
    cursor.execute("insert into holdings (portfolio, security) values (?, ?)",
                   (portfolio_number, security_pk))
    new_pk = cursor.lastrowid
    connection.commit()
    return new_pk


def add_portfolio(name, description):
    with sql_connection() as c:
        cursor = c.cursor()
        cursor.execute("INSERT INTO portfolios (name, description) values (?, ?)", (name, description))
        new_pk = cursor.lastrowid
        c.commit()
        return new_pk
