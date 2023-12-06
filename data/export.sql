--
-- File generated with SQLiteStudio v3.3.3 on Tue Oct 24 19:28:13 2023
--
-- Text encoding used: System
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: holdings
DROP TABLE IF EXISTS holdings;

CREATE TABLE holdings (
    PK          INTEGER PRIMARY KEY AUTOINCREMENT
                        UNIQUE
                        NOT NULL,
    create_date INTEGER DEFAULT (CURRENT_TIMESTAMP),
    portfolio   INTEGER REFERENCES portfolios (PK) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                                                   MATCH SIMPLE
                        NOT NULL,
    name        TEXT    NOT NULL,
    ticker      TEXT    NOT NULL,
    description TEXT    DEFAULT "",
    units       INTEGER DEFAULT (0),
    is_priced   INTEGER DEFAULT (0),
    last_price  REAL,
    price_date  INTEGER
);

INSERT INTO holdings (
                         PK,
                         create_date,
                         portfolio,
                         name,
                         ticker,
                         description,
                         units,
                         is_priced,
                         last_price,
                         price_date
                     )
                     VALUES (
                         1,
                         '2023-10-20 22:30:38',
                         6,
                         'Apple',
                         'AAPL',
                         'you know what apple is',
                         0,
                         0,
                         NULL,
                         NULL
                     );


-- Table: portfolios
DROP TABLE IF EXISTS portfolios;

CREATE TABLE portfolios (
    PK          INTEGER PRIMARY KEY AUTOINCREMENT
                        NOT NULL
                        UNIQUE,
    name        TEXT    NOT NULL,
    description TEXT    DEFAULT "",
    create_date INTEGER DEFAULT (CURRENT_TIMESTAMP) 
);

INSERT INTO portfolios (
                           PK,
                           name,
                           description,
                           create_date
                       )
                       VALUES (
                           1,
                           'test',
                           '',
                           1697842717
                       );

INSERT INTO portfolios (
                           PK,
                           name,
                           description,
                           create_date
                       )
                       VALUES (
                           2,
                           'test',
                           '',
                           1697842717
                       );

INSERT INTO portfolios (
                           PK,
                           name,
                           description,
                           create_date
                       )
                       VALUES (
                           3,
                           'test',
                           '',
                           1697842717
                       );

INSERT INTO portfolios (
                           PK,
                           name,
                           description,
                           create_date
                       )
                       VALUES (
                           4,
                           'name',
                           '',
                           1697842717
                       );

INSERT INTO portfolios (
                           PK,
                           name,
                           description,
                           create_date
                       )
                       VALUES (
                           5,
                           'name',
                           '',
                           1697842717
                       );

INSERT INTO portfolios (
                           PK,
                           name,
                           description,
                           create_date
                       )
                       VALUES (
                           6,
                           'US Technology Leaders',
                           'Invests in the top 50 US technology companies by market capitalization. Aims to maintain a balanced weighting. Recalibrating is carried out biweekly.',
                           1697842717
                       );


-- Table: trades
DROP TABLE IF EXISTS trades;

CREATE TABLE trades (
    PK                INTEGER PRIMARY KEY AUTOINCREMENT
                              NOT NULL
                              UNIQUE,
    portfolio_holding INTEGER REFERENCES holdings (PK) ON DELETE CASCADE
                                                       ON UPDATE CASCADE
                                                       MATCH SIMPLE
                              NOT NULL,
    type              TEXT    NOT NULL,
    units             INTEGER NOT NULL,
    amount            REAL    NOT NULL,
    creation_date     INTEGER NOT NULL
                              DEFAULT (CURRENT_TIMESTAMP) 
);


-- View: holdings_expanded
DROP VIEW IF EXISTS holdings_expanded;
CREATE VIEW holdings_expanded AS
    SELECT PK,
           strftime('%d/%m/%Y', create_date, 'unixepoch') AS create_date,
           portfolio,
           name,
           ticker,
           description,
           units,
           is_priced,
           last_price,
           price_date
      FROM holdings;


-- View: portfolio_holdings
DROP VIEW IF EXISTS portfolio_holdings;
CREATE VIEW portfolio_holdings AS
    SELECT h.PK AS holding_pk,
           h.create_date AS holding_create_date,
           h.name AS holding_name,
           h.ticker AS ticker,
           h.description AS holding_description,
           h.units AS units,
           h.is_priced AS is_priced,
           h.last_price AS last_price,
           h.price_date AS price_date,
           p.PK AS portfolio_pk,
           p.name AS portfolio_name,
           p.description AS portfolio_description,
           p.create_date AS portfolio_create_date
      FROM holdings h
           JOIN
           portfolios p ON h.portfolio = p.PK;


-- View: portfolios_expanded
DROP VIEW IF EXISTS portfolios_expanded;
CREATE VIEW portfolios_expanded AS
    SELECT p.PK AS PK,
           p.name AS name,
           p.description AS description,
           (
               SELECT count(PK) 
                 FROM holdings h
                WHERE h.portfolio = p.PK
           )
           AS holdings_count,
           strftime('%d/%m/%Y', create_date, 'unixepoch') AS create_date
      FROM portfolios p;


COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
