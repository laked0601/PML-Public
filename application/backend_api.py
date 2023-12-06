from requests import get


class Ticker:
    def __init__(self, **kwargs):
        self.security_pk = None
        self.PK = None
        self.name = None
        self.portfolio = None
        self.ticker = None
        self.description = None
        self.market_cap = None
        self.homepage_url = None
        self.logo_url = None
        self.icon_url = None
        self.share_class_shares_outstanding = None
        self.weighted_shares_outstanding = None
        self.round_lot = None
        self.active = None
        self.primary_exchange = None
        self.type = None
        self.sic_code = None
        self.market = None
        self.last_price_date = None
        self.last_close_price = None
        self.unrealised_gl = None
        self.allocation = None
        self.market_value = None
        for k, v in kwargs.items():
            setattr(self, k, v)


class tickerSearch:
    def __init__(self, ticker):
        self.rows = []
        self.headers = []
        self.tickers = []
        self.count = None
        r = get(f"https://danl.info/portfolio-analysis/api/tickers?ticker={ticker}&active=1", verify=False)
        res = r.json()
        headers = [(head, i) for i, head in enumerate(res["headers"])]
        # [("PK", 0), ("name", 1), ("description", 2)...]
        for row in res["rows"]:
            ticker_data = {}
            for header, index in headers:
                ticker_data[header] = row[index]
            # {"PK": 7237, "name": "Agilent Technologies Inc.", ...}
            self.tickers.append(Ticker(**ticker_data))

    def result_count(self):
        return len(self.tickers)

    def first_result(self):
        return self.tickers[0]

    def __iter__(self):
        for x in self.tickers:
            yield x


def get_api_price(ticker, date):
    r = get("https://danl.info/portfolio-analysis/api/eod_price",
            params={"ticker": ticker, "date": date.isoformat()},
            verify=False)
    response_json = r.json()
    if len(response_json["rows"]) == 0:
        return None
    return response_json["rows"][0]
