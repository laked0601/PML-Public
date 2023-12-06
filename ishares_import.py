import requests
import csv
import re
import json
from sqlite_interaction import sql_connection
from application.accounting import add_portfolio, add_holding, trade
from datetime import date


# A temporary file, to download half a dozen ishares etfs
urls_tuple = (
    "https://www.ishares.com/us/products/239737/ishares-global-100-etf",
    "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf",
    "https://www.ishares.com/us/products/251614/ishares-msci-usa-momentum-factor-etf",
    "https://www.ishares.com/us/products/264623/ishares-core-dividend-growth-etf",
    "https://www.ishares.com/us/products/256101/ishares-msci-usa-quality-factor-etf"
)
title_re = re.compile("<title>(.*?) \| (.*?)<", re.MULTILINE)
description_re = re.compile("<meta name=\"description\" .*?content=\"(.*?)\"", re.MULTILINE)
ajax_url_re = re.compile('<div id=\"allHoldingsTab\" data-ajaxUri=\"(.*?)\?', re.MULTILINE)


class r:
    text = ""


class portfolio:
    def __init__(self):
        self.PK = None
        self.title = None
        self.description = None
        self.ticker = None
        self.ajax_url = None
        self.holdings = []

    @staticmethod
    def from_url(url, session):
        new_portfolio = portfolio()
        r = session.get(url)
        title_res = title_re.findall(r.text)[0]
        new_portfolio.title, new_portfolio.ticker = title_res[0], title_res[1]
        new_portfolio.description = (f"The following is a simplified replica of an investment fund provided by "
                                     f"BlackRock Investment Management from 30th June 2022 and will not mirror the "
                                     f"returns of this fund. For further details of the fund these holdings "
                                     f"are based on, please visit {url}\n\nAn expanded description of the fund from "
                                     f"BlackRock is as follows: {description_re.search(r.text).group(1)}")
        new_portfolio.ajax_url = "https://www.ishares.com" + ajax_url_re.search(r.text).group(1)
        return new_portfolio

    def allocate_to_capital(self, capital):
        top_holdings = list(sorted(self.holdings, key=lambda h: h.weight, reverse=True)[0:25])
        sum_weights = sum([h.weight for h in top_holdings])
        weight_factor = 100 / sum_weights
        sum_cost = 0.0
        for h in top_holdings:
            target_weight = weight_factor * h.weight / 100
            h.weight = target_weight
            target_cost = target_weight * capital
            best_units = int(target_cost / h.price)
            h.units = best_units
            best_cost = h.price * best_units
            h.amount = round(best_cost, 2)
        self.holdings = top_holdings

    def portfolio_value(self):
        val = 0.0
        for h in self.holdings:
            val = round(val + h.amount, 2)
        return val


class holding:
    def __init__(self):
        self.PK = None
        self.ticker = None
        self.price = None
        self.units = None
        self.amount = None
        self.weight = None

    @staticmethod
    def from_row(json_row):
        new_holding = holding()
        new_holding.ticker = json_row[0]
        new_holding.price = json_row[11]["raw"]
        new_holding.weight = json_row[5]["raw"]
        return new_holding


def extract_holdings_data(ajax_url, session):
    r = session.get(ajax_url, params={"tab": "all", "fileType": "json", "asOfDate": 20220630})
    holdings = []
    json_data = json.loads(r.content.decode('utf-8-sig'))
    for row in json_data["aaData"]:
        try:
            new_holding = holding.from_row(row)
        except:
            continue
        holdings.append(new_holding)
    return holdings


CAPITAL = 100_000
transaction_date = date(2022, 6, 30)


with sql_connection() as c:
    cursor = c.cursor()
    with requests.session() as s:
        for url in urls_tuple:
            pf = portfolio.from_url(url, s)
            cursor.execute("select PK from portfolios where name = ?", (pf.title,))
            if cursor.fetchone() is not None:
                print(f"Ignoring {pf.title}...")
                continue
            pf.PK = add_portfolio(pf.title, pf.description)
            pf.holdings = extract_holdings_data(pf.ajax_url, s)
            pf.allocate_to_capital(CAPITAL)
            for h in pf.holdings:
                try:
                    h.PK = add_holding(h.ticker, pf.PK, cursor=cursor, connection=c)
                    trade(PK=h.PK, units=h.units, amount=h.amount, transaction_type="Buy", trade_date=transaction_date,
                          connection=c, cursor=cursor)
                except ValueError as e:
                    print(e)

