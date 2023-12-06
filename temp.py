import requests
from sqlite_interaction import sql_connection
from datetime import date, timedelta
from time import mktime


with sql_connection() as c:
    cursor = c.cursor()
    todays_date = date.today()
    cursor.execute("select PK, ticker from securities")
    queue = []
    with requests.session() as s:
        for (PK, ticker) in cursor.fetchall():
            cursor.execute("select distinct date from prices where security = ?", (PK,))
            existing_prices = set([x[0] for x in cursor.fetchall()])
            r = s.get("http://danl.info/portfolio-analysis/api/eod_price",
                      params={"ticker": ticker, "date": (todays_date - timedelta(days=720)).isoformat(),
                              "end_date": todays_date})
            for date_iso_string, price in r.json()["rows"]:
                price_time = mktime(date.fromisoformat(date_iso_string).timetuple())
                if price_time in existing_prices:
                    continue
                queue.append(
                    (PK, price_time, price)
                )
                if len(queue) > 500:
                    cursor.executemany("INSERT OR IGNORE INTO prices (security, date, price) VALUES (?, ?, ?)", queue)
                    c.commit()
                    queue = []
    cursor.executemany("INSERT OR IGNORE INTO prices (security, date, price) VALUES (?, ?, ?)", queue)
    c.commit()

