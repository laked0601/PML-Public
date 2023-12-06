from sqlite_interaction import sql_connection
from datetime import datetime

with sql_connection() as c:
    cursor = c.cursor()
    cursor.execute("insert into portfolios(name, create_date)values (?, ?)", ("name", datetime.today()))
    c.commit()