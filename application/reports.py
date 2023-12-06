import requests
from webserver_app import wsapp
from flask import render_template, request
from globals import BASE_ENDPOINT, THIS_SERVER_URL
from errors import not_found
from application.portfolios import PortfolioForm
from sqlite_interaction import sql_connection
import application.accounting as accounting
from datetime import date, datetime
from globals import THIS_SERVER_DIR
import matplotlib.pyplot as plt
import base64
import os
from time import sleep, mktime


micro_rgb_params = ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1))
short_rgb_params = (1, 0.5, 0.75, 0.875, 0.625, 0.9375, 0.5625)
short_params_len = len(short_rgb_params) * len(micro_rgb_params)
ASSET_ALLOCATION_LOCATION = THIS_SERVER_DIR + "reports/asset_values.png"
PERFORMANCE_GRAPH_LOCATION = THIS_SERVER_DIR + "reports/performance_graph.png"


def short_rgb_loop(stop=short_params_len):
    count = 0
    for sht in short_rgb_params:
        for mic in micro_rgb_params:
            yield [i * sht for i in mic]
            count += 1
            if count >= stop:
                break
        if count >= stop:
            break


def get_chart_colors(assets):
    rgb_values = None
    if short_params_len >= len(assets):
        rgb_values = []
        for rgb in short_rgb_loop(stop=len(assets)):
            rgb_values.append(rgb)
    return rgb_values


def make_assets_chart(assets):
    fig, ax = plt.subplots()
    labels = []
    for inv in assets:
        labels.append(f"{round(100 * inv.allocation)}% {inv.name}")
    ax.pie(
        x=[inv.allocation for inv in assets],
        colors=get_chart_colors(assets),
        wedgeprops=dict(width=0.3),
        startangle=-40
    )
    plt.legend(
        labels=labels,
        loc="upper right",
        bbox_to_anchor=(2, 0.9)
    )
    plt.savefig(ASSET_ALLOCATION_LOCATION, bbox_inches='tight')


def build_asset_allocation(portfolio, holdings):
    """
    If the number of holdings is greater than 15, find the top holdings by allocation and use them. Otherwise, use all
    holdings. Create the charts and table elements to use
    :param holdings:
    :return:
    """
    for h in holdings:
        h.allocation = h.market_value / portfolio.total_market_value
    key_holdings = sorted(holdings, key=lambda h: h.allocation, reverse=True)[0:15]
    make_assets_chart(key_holdings)
    with open(ASSET_ALLOCATION_LOCATION, 'rb') as rf:
        encoded_string = base64.b64encode(rf.read()).decode('utf-8')
    return f"data:image/png;base64,{encoded_string}"


def get_period(timestamp):
    timestamp_datetime = datetime.fromtimestamp(timestamp)
    return timestamp_datetime.year, timestamp_datetime.month


def empty_periods(from_period, to_period):
    for i in range(from_period[0] * 12 + from_period[1] + 1, to_period[0] * 12 + to_period[1]):
        year = i // 12
        yield year, i - year * 12


def get_last_month_second(year, month):
    if month == 12:
        last_month_second = datetime(year + 1, 1, 1).timestamp() - 1
    else:
        last_month_second = datetime(year, month + 1, 1).timestamp() - 1
    return last_month_second


def get_market_value(cursor, year, month, holding_data):
    market_value = 0.0
    holding_pks = [str(int(x)) for x in holding_data.keys()]
    missing_pks = {}
    last_month_second = get_last_month_second(year, month)
    for _ in range(2):
        cursor.execute(f"SELECT sec.PK, hld.PK, res.date, sec.ticker, px.price FROM securities sec "
                       f"LEFT JOIN ("
                       f"    SELECT security, MAX(date) AS date FROM prices "
                       f"    WHERE date BETWEEN ? - 86400 * 5 AND ? "
                       f"    GROUP BY security "
                       f") res ON sec.PK = res.security "
                       f"left join holdings hld on hld.security = sec.PK "
                       f"LEFT JOIN prices px ON px.security = sec.PK AND px.date = res.date "
                       f"where hld.PK in ({','.join(holding_pks)})",  # godawful solution
                       (last_month_second, last_month_second))
        for (security_pk, hld_pk, price_timestamp, ticker, price) in cursor.fetchall():
            if price is not None and hld_pk in holding_data:
                market_value = round(holding_data[hld_pk][1] * price + market_value, 2)
            else:
                missing_pks[str(hld_pk)] = security_pk
        if len(missing_pks) == 0:
            break
        with requests.session() as s:
            end_date = date.fromtimestamp(last_month_second)
            for hld_pk, security_pk in missing_pks.items():
                r = s.get(THIS_SERVER_URL + "/get-price", params={"PK": security_pk, "date": end_date.isoformat()},
                          verify=False)
                # res = r.json()

        holding_pks = list(missing_pks.keys())
    return market_value


def make_performance_chart(portfolio_number, cursor):
    cursor.execute("select tr.* from trades tr "
                   "left join holdings h on tr.portfolio_holding = h.PK "
                   "where h.portfolio = ? "
                   "order by tr.trade_date, tr.portfolio_holding, tr.type", (portfolio_number,))
    row = cursor.fetchone()
    monthly_cost = []
    monthly_mval = []
    period_dates = []
    if row is not None:
        total_units = row[3]
        total_cost = row[4]
        active_holding = row[1]
        current_period = get_period(row[6])
        holding_data = {active_holding: [total_cost, total_units]}
        for (trade_pk, holding_pk, transaction_type, units, amount, creation_date, trade_date) in cursor.fetchall():
            if current_period != get_period(trade_date):
                monthly_mval.append(get_market_value(cursor, current_period[0], current_period[1], holding_data))
                total_cost = 0.0
                for v in holding_data.values():
                    total_cost = round(total_cost + v[0], 2)

                monthly_cost.append(total_cost)
                period_dates.append(date.fromtimestamp(get_last_month_second(current_period[0], current_period[1])))

                new_period = get_period(trade_date)
                for m in empty_periods(current_period, new_period):
                    monthly_cost.append(total_cost)
                    monthly_mval.append(get_market_value(cursor, m[0], m[1], holding_data))
                    period_dates.append(date.fromtimestamp(get_last_month_second(m[0], m[1])))

                current_period = new_period

            if holding_pk != active_holding:
                active_holding = holding_pk
                if active_holding not in holding_data:
                    holding_data[active_holding] = [0.0, 0]

            if transaction_type == "Buy":
                holding_data[active_holding][0] = round(holding_data[active_holding][0] + amount, 2)
                holding_data[active_holding][1] += units
            else:  # Sell
                wac_per_unit = holding_data[active_holding][0] / holding_data[active_holding][1]
                holding_data[active_holding][1] -= units
                if holding_data[active_holding][1] == 0:
                    del holding_data[active_holding]
                else:
                    holding_data[active_holding][0] = round(holding_data[active_holding][1] * wac_per_unit, 2)
        monthly_mval.append(get_market_value(cursor, current_period[0], current_period[1], holding_data))
        total_cost = 0.0
        for v in holding_data.values():
            total_cost = round(total_cost + v[0], 2)

        monthly_cost.append(total_cost)
        period_dates.append(date.fromtimestamp(get_last_month_second(current_period[0], current_period[1])))

        new_period = get_period(datetime.today().timestamp())
        for m in empty_periods(current_period, new_period):
            monthly_cost.append(total_cost)
            monthly_mval.append(get_market_value(cursor, m[0], m[1], holding_data))
            period_dates.append(date.fromtimestamp(get_last_month_second(m[0], m[1])))

    x_axis = [x.strftime("%d/%m/%Y") for x in period_dates]

    plt.figure()

    # Plotting the monthly cost in red
    plt.plot(x_axis, monthly_cost, color='red', label='Weighted Average Cost')

    # Plotting the monthly mval in blue
    plt.plot(x_axis, monthly_mval, color='blue', label='Market Value')

    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    plt.savefig(PERFORMANCE_GRAPH_LOCATION, bbox_inches='tight')

    with open(PERFORMANCE_GRAPH_LOCATION, 'rb') as rf:
        encoded_string = base64.b64encode(rf.read()).decode('utf-8')
    return f"data:image/png;base64,{encoded_string}"


def annualised_return(portfolio):
    difference_in_years = (mktime(date.today().timetuple()) - portfolio.first_trade_date) / (60 * 60 * 24 * 365)
    return (portfolio.total_market_value / portfolio.total_cost) ** (1 / difference_in_years) * 100 - 100


@wsapp.route(BASE_ENDPOINT + "/reports/performance.html", methods=["GET"])
def reports_performance():
    with sql_connection() as c:
        cursor = c.cursor()
        form = PortfolioForm(request.args, cursor=cursor, meta={"csrf": False})
        if form.validate():
            portfolio = accounting.get_portfolio(PK=form.number.data, connection=c, cursor=cursor)
            holdings = accounting.get_holdings(portfolio_number=form.number.data, connection=c, cursor=cursor)
            for _ in range(3):
                try:
                    allocation_chart = build_asset_allocation(portfolio, holdings)
                    break
                except RuntimeError:
                    sleep(0.5)
                    pass
            else:
                os.remove(ASSET_ALLOCATION_LOCATION)
            for _ in range(3):
                try:
                    performance_chart = make_performance_chart(form.number.data, cursor)
                    break
                except RuntimeError:
                    sleep(0.5)
                    pass
            else:
                os.remove(PERFORMANCE_GRAPH_LOCATION)

            return render_template("portfolio_performance.html",
                                   portfolio=portfolio,
                                   report_date=date.today().strftime("%d/%m/%Y"),
                                   portfolio_start=date.fromtimestamp(portfolio.first_trade_date).strftime("%d/%m/%Y"),
                                   allocation_chart=allocation_chart,
                                   performance_chart=performance_chart,
                                   holdings=holdings,
                                   annualised_return=annualised_return(portfolio),
                                   total_return_percentage=portfolio.total_unrealised_gl / portfolio.total_cost * 100,
                                   BASE_ENDPOINT=BASE_ENDPOINT)
    return not_found()
