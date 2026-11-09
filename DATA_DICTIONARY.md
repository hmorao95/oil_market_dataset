# Data dictionary

All series are monthly, from 1974m1. Raw inputs are in `data/raw/` as
`period,value` CSVs.

## `poil`: real oil price

`100 · ln(RAC_t / CPI_t × 100)`

- `RAC`: refiners' acquisition cost of imported crude oil, $/bbl. EIA
  `PET.R1300____3.M` (`data/raw/eia_rac_imported.csv`).
- `CPI`: CPI-U, all items, seasonally adjusted, 1982–84 = 100. BLS
  `CUSR0000SA0` (`data/raw/bls_cpi.csv`). BLS did not publish October 2025; that
  month is filled by log-linear interpolation.

## `oilprod`: world crude oil production growth

`100 · [ln(Q_t) − ln(Q_{t−1})]`

- `Q`: world production of crude oil including lease condensate, thousand
  barrels per day. EIA international data, productId 57, activityId 1, region
  WORL (`data/raw/eia_world_crude.csv`).

## `oilstocks`: change in global crude oil inventories

`S_t − S_{t−1}`, million barrels, where `S` is the Kilian and Murphy (2014) proxy:

`S_t = OECD_t × (USCRUDE_t / USTOTAL_t)`

- `OECD`: OECD petroleum stocks (crude and products), million barrels. EIA
  international data, productId 5, activityId 5, region OECD
  (`data/raw/eia_oecd_stocks.csv`). Used from 1988m1; the EIA series has gaps
  and a level break before then. Earlier months are extended backward with the
  growth rate of `USTOTAL`.
- `USCRUDE`: US crude oil stocks including the SPR. EIA `PET.MCRSTUS1.M`
  (Datastream EIA1533).
- `USTOTAL`: US stocks of crude oil and petroleum products including the SPR.
  EIA `PET.MTTSTUS1.M` (Datastream EIA1541).

The OECD series corresponds to Datastream EIA1976.

## `gecon`: world economic conditions

The column "Standardized GECON" of `GECON_indicator.xlsx` from Christiane
Baumeister's datasets page (Baumeister, Korobilis and Lee 2022). The indicator
is re-estimated every month, so past values change with each vintage.

## `igrea`: global real economic activity

Kilian's (2009) index of global real economic activity, in levels: a
cumulated, deflated and detrended index of dry-bulk ocean shipping rates, from
`igrea.xlsx` on the Federal Reserve Bank of Dallas website
(`data/raw/kilian_igrea.csv`). The detrending is redone on the full sample at
each update, so the whole history changes slightly with each vintage.

## `wipi`: world industrial production

`100 · ln(IP_t)`, industrial production of the OECD plus six major non-OECD
economies (Brazil, China, India, Indonesia, Russia, South Africa), from
Baumeister and Hamilton (2019), `OECD_plus6_industrial_production.xlsx` on
Christiane Baumeister's datasets page (`data/raw/bh_world_ip.csv`). The source
file is revised and extended monthly.

## `gprh`: geopolitical risk

`100 · ln(GPRH_t)`, the historical geopolitical risk index of Caldara and
Iacoviello (2022), from `data_gpr_export.xls` on matteoiacoviello.com.

## Revisions

EIA revises recent production and stock data, Baumeister revises the whole
WECI history and the world IP series, Kilian's index is re-detrended at each
update, and BLS revises seasonal factors. A rebuild on a later date will
differ from an earlier one in those places.
