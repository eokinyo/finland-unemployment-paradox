#!/usr/bin/env python3
"""
Finland tops the EU jobless table. Is it as bad as it looks?

Reproduces the numbers, the comparison table and the charts for Elly Okinyo's article on
Finland's unemployment rate and employment rate (October 2026).

Three steps, run in order by main():
  1. download  - query the Eurostat and Statistics Finland (StatFin) APIs
                 (responses cached in data/raw/, git-ignored)
  2. analyse   - headline numbers N1-N14, Nordic table T1, youth/student split
                 (CSVs and a Markdown table in outputs/)
  3. charts    - four charts, PNG and SVG (outputs/charts/)

Sources (public APIs, no keys; downloaded at run time, nothing is committed to the repo):
  * Eurostat dissemination API (JSON-stat 2.0): une_rt_m, une_rt_q, lfsi_emp_q,
    lfsa_pganws, edat_lfse_20, edat_lfse_18
  * Statistics Finland, StatFin PxWeb API: Labour Force Survey tables 135z and 13am

Run:  python unemployment_paradox.py            (add --refresh to download again)
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
import time
from pathlib import Path

import requests
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # no GUI needed; works on Windows/macOS/Linux/headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Reference periods are pinned to the releases used in the article, so the numbers do not
# move when newer data come out (only revisions can change them). To update, change these.
MONTH = "2026-08"          # latest month in une_rt_m (Eurostat release of 1 Oct 2026)
QUARTER = "2026-Q2"        # latest quarter in une_rt_q / lfsi_emp_q
YEAR = "2025"              # latest year of the annual LFS tables
START_MONTH = "2015-01"    # start of the monthly line chart and the low/high search
START_QUARTER = "2015-Q1"  # start of the quarterly employment/activity chart

# Published values used as checks (Eurostat euro indicators, 1 Oct 2026:
# https://ec.europa.eu/eurostat/web/products-euro-indicators/w/3-01102026-ap).
RELEASE_FI_UR = 10.3       # Finland, August 2026 (trend)
RELEASE_EU_UR = 6.1        # EU27, August 2026 (seasonally adjusted)

EU = "EU27_2020"
EU27 = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU",
        "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"]
# Eurostat's monthly release uses the trend-cycle (TC) series for these countries and the
# seasonally adjusted (SA) series for all others.
TC_GEOS = {"DE", "NL", "FI", "SE"}
NORDIC = {"FI": ("Finland", "#c0392b"), "SE": ("Sweden", "#1f77b4"),
          "DK": ("Denmark", "#2ca02c"), EU: ("EU27", "#555555")}

EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
STATFIN_API = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/tyti/"

SRC_ES = "Source: Eurostat ({}); author's calculations."

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_DIR = BASE_DIR / "outputs"
CHART_DIR = OUT_DIR / "charts"

TIMEOUT = 120  # seconds
RETRIES = 3
USER_AGENT = "finland-unemployment-paradox/1.0 (+python-requests)"


# --------------------------------------------------------------------------- #
# Step 1: download
# --------------------------------------------------------------------------- #
def _cached(name: str, key: object, fetch, refresh: bool) -> dict:
    """Return a JSON response from data/raw/ or fetch it (with retries) and cache it."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()[:10]
    path = RAW_DIR / f"{name}_{digest}.json"
    if path.exists() and not refresh:
        print(f"Using cached {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))
    err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = fetch()
            r.raise_for_status()
            data = r.json()
            path.write_text(json.dumps(data), encoding="utf-8")
            print(f"Downloaded {name} ({len(r.content) / 1e3:.0f} kB)")
            return data
        except (requests.RequestException, ValueError) as e:
            err = e
            time.sleep(2 * attempt)
    sys.exit(f"Could not download {name} ({err}). Check the internet connection and run again.")


def jsonstat_to_frame(d: dict) -> pd.DataFrame:
    """Flatten a JSON-stat 2.0 dataset (Eurostat or PxWeb) into a tidy DataFrame."""
    ids = d["id"]
    cats = []
    for dim in ids:
        idx = d["dimension"][dim]["category"]["index"]
        cats.append(sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx))
    values, status = d.get("value", {}), d.get("status", {}) or {}
    rows = []
    for n, combo in enumerate(itertools.product(*cats)):
        v = values.get(str(n)) if isinstance(values, dict) else values[n]
        if v is None:
            continue
        flag = status.get(str(n)) if isinstance(status, dict) else (status[n] if status else None)
        rows.append((*combo, v, flag or ""))
    return pd.DataFrame(rows, columns=[*ids, "value", "flag"])


def eurostat(code: str, refresh: bool, **params) -> pd.DataFrame:
    """Query one Eurostat dataset (filters as keyword arguments; lists allowed)."""
    params = {"lang": "en", **params}
    data = _cached(f"eurostat_{code}", [code, params],
                   lambda: requests.get(EUROSTAT_API + code, params=params, timeout=TIMEOUT,
                                        headers={"User-Agent": USER_AGENT}), refresh)
    return jsonstat_to_frame(data)


def statfin(table: str, selection: dict[str, list[str]], refresh: bool) -> pd.DataFrame:
    """Query one StatFin PxWeb table (tyti = Labour Force Survey) as JSON-stat 2.0."""
    body = {"query": [{"code": k, "selection": {"filter": "item", "values": v}}
                      for k, v in selection.items()],
            "response": {"format": "json-stat2"}}
    data = _cached(f"statfin_{table}", [table, body],
                   lambda: requests.post(f"{STATFIN_API}{table}.px", json=body, timeout=TIMEOUT,
                                         headers={"User-Agent": USER_AGENT}), refresh)
    return jsonstat_to_frame(data)


def months(start: str, end: str) -> list[str]:
    return [p.strftime("%YM%m") for p in pd.period_range(start, end, freq="M")]


def download(refresh: bool) -> dict[str, pd.DataFrame]:
    geos = EU27 + [EU]
    nordic = list(NORDIC)
    d = {
        # Monthly unemployment rate, total and under 25, SA and trend (N1-N3, N9, N14, C2)
        "une_rt_m": eurostat("une_rt_m", refresh, geo=geos, sex="T", age=["TOTAL", "Y_LT25"],
                             unit="PC_ACT", s_adj=["SA", "TC"], sinceTimePeriod=START_MONTH,
                             untilTimePeriod=MONTH),
        # Quarterly unemployment rate 15-74, SA (N7, C1)
        "une_rt_q": eurostat("une_rt_q", refresh, geo=geos, sex="T", age="Y15-74",
                             unit="PC_ACT", s_adj="SA", time=QUARTER),
        # Quarterly employment and activity rates 20-64, SA (N4-N8, C1, C3)
        "lfsi_emp_q": eurostat("lfsi_emp_q", refresh, geo=geos, sex="T", age="Y20-64",
                               unit="PC_POP", indic_em=["EMP_LFS", "ACT"], s_adj="SA",
                               sinceTimePeriod=START_QUARTER, untilTimePeriod=QUARTER),
        # Annual population 15-24 by labour status (N10, C4)
        "lfsa_pganws": eurostat("lfsa_pganws", refresh, geo=nordic, sex="T", age="Y15-24",
                                citizen="TOTAL", unit="THS_PER",
                                wstatus=["POP", "ACT", "EMP", "UNE"], time=YEAR),
        # Unemployed and NOT in education or training, % of population 15-24 (N11, C4)
        "edat_lfse_20": eurostat("edat_lfse_20", refresh, geo=nordic, sex="T", age="Y15-24",
                                 training="NO_FE_NO_NFE", wstatus="UNE", unit="PC", time=YEAR),
        # Employed, in / not in education or training, % of population 15-24 (N12)
        "edat_lfse_18": eurostat("edat_lfse_18", refresh, geo=nordic, sex="T", age="Y15-24",
                                 wstatus="EMP", training=["FE_NFE", "NO_FE_NO_NFE"], unit="PC",
                                 time=YEAR),
        # StatFin LFS key indicators: trend and SA series (N14 cross-check)
        "135z": statfin("135z", {
            "contentscode": ["tyottaste_trendi", "Tyottaste_kausi", "tyti-Tyottomyysaste",
                             "Tyollaste_20_64_trendi", "Tyollaste_20_64_kausi"],
            "timeperiod_m": months(START_MONTH, MONTH)}, refresh),
        # StatFin young people in education and the labour market (N13)
        "13am": statfin("13am", {
            "timeperiod_y": [YEAR], "sukupuoli_9_20180101": ["SSS"],
            "ikaryhma_19_20190101": ["15-24"],
            "contentscode": ["tyti-Vaesto", "tyti-Tyolliset", "Tyolliset_opisk_laaja",
                             "Ei_tyoll", "Eityolliset_opisk_laaja"]}, refresh),
    }
    return d


# --------------------------------------------------------------------------- #
# Step 2: analyse
# --------------------------------------------------------------------------- #
def pick(df: pd.DataFrame, **filters) -> pd.DataFrame:
    for k, v in filters.items():
        df = df[df[k].isin(v if isinstance(v, (list, set, tuple)) else [v])]
    return df


def one(df: pd.DataFrame, **filters) -> float:
    s = pick(df, **filters)["value"]
    if len(s) != 1:
        raise ValueError(f"expected one value for {filters}, got {len(s)}")
    return float(s.iloc[0])


def headline_series(m: pd.DataFrame, age: str, period: str) -> pd.Series:
    """Unemployment rate by country for one month, using the series the release uses
    (trend for DE, NL, FI, SE; seasonally adjusted for the rest and the EU)."""
    out = {}
    for g in EU27 + [EU]:
        adj = "TC" if g in TC_GEOS else "SA"
        s = pick(m, geo=g, age=age, s_adj=adj, time=period)["value"]
        if len(s):
            out[g] = float(s.iloc[0])
    return pd.Series(out, dtype=float)


def analyse(d: dict[str, pd.DataFrame]) -> dict:
    m, uq, eq = d["une_rt_m"], d["une_rt_q"], d["lfsi_emp_q"]
    head: list[dict] = []

    def add(id_, label, value, unit, period, source):
        head.append({"id": id_, "label": label, "value": value, "unit": unit,
                     "period": period, "source": source})

    # N1-N3: headline unemployment rate and rank, latest month
    ur = headline_series(m, "TOTAL", MONTH)
    members = ur.drop(EU, errors="ignore")
    rank = members.rank(ascending=False, method="min")
    missing_m = sorted(set(EU27) - set(members.index))
    add("fi_ur", "Finland unemployment rate, 15-74 (trend, as in the release)", ur["FI"],
        "% of labour force", MONTH, "Eurostat une_rt_m, s_adj=TC")
    add("eu_ur", "EU27 unemployment rate, 15-74 (seasonally adjusted)", ur[EU],
        "% of labour force", MONTH, "Eurostat une_rt_m, s_adj=SA")
    add("fi_rank_ur", f"Finland's rank among {len(members)} EU members (1 = highest)",
        int(rank["FI"]), "rank", MONTH, "Eurostat une_rt_m, TC for DE/NL/FI/SE, SA for others")
    add("fi_ur_sa", "Finland unemployment rate, 15-74 (seasonally adjusted, for reference)",
        one(m, geo="FI", age="TOTAL", s_adj="SA", time=MONTH), "% of labour force", MONTH,
        "Eurostat une_rt_m, s_adj=SA")

    # N4-N7: employment rate 20-64 and cross-country correlation, latest quarter
    er = pick(eq, indic_em="EMP_LFS", time=QUARTER).set_index("geo")["value"]
    act = pick(eq, indic_em="ACT", time=QUARTER).set_index("geo")["value"]
    urq = uq.set_index("geo")["value"]
    sc = pd.DataFrame({"unemployment_rate_15_74": urq, "employment_rate_20_64": er,
                       "activity_rate_20_64": act}).reindex(EU27 + [EU])
    sc.index.name = "geo"
    both = sc.loc[EU27].dropna(subset=["unemployment_rate_15_74", "employment_rate_20_64"])
    er_rank = sc.loc[EU27, "employment_rate_20_64"].dropna().rank(ascending=False, method="min")
    corr = both["unemployment_rate_15_74"].corr(both["employment_rate_20_64"])
    add("fi_er", "Finland employment rate, 20-64 (seasonally adjusted)", sc.at["FI", "employment_rate_20_64"],
        "% of population", QUARTER, "Eurostat lfsi_emp_q, EMP_LFS, PC_POP, SA")
    add("eu_er", "EU27 employment rate, 20-64 (seasonally adjusted)", sc.at[EU, "employment_rate_20_64"],
        "% of population", QUARTER, "Eurostat lfsi_emp_q, EMP_LFS, PC_POP, SA")
    add("fi_rank_er", f"Finland's employment-rate rank among {int(er_rank.count())} EU members (1 = highest)",
        int(er_rank["FI"]), "rank", QUARTER, "Eurostat lfsi_emp_q")
    add("corr", f"Pearson r, unemployment rate vs employment rate 20-64, {len(both)} EU members",
        round(corr, 3), "r", QUARTER, "Eurostat une_rt_q (Y15-74, SA) and lfsi_emp_q")
    slope = both["employment_rate_20_64"].cov(both["unemployment_rate_15_74"]) / both["unemployment_rate_15_74"].var()
    icept = both["employment_rate_20_64"].mean() - slope * both["unemployment_rate_15_74"].mean()
    fitted_fi = icept + slope * both.at["FI", "unemployment_rate_15_74"]
    add("fi_er_vs_fitted", "Finland employment rate minus the least-squares line across EU members "
        "at Finland's unemployment rate", round(both.at["FI", "employment_rate_20_64"] - fitted_fi, 1),
        "percentage points", QUARTER, "Eurostat une_rt_q and lfsi_emp_q (derived)")
    add("fi_ur_q", "Finland unemployment rate, 15-74 (quarterly, seasonally adjusted)",
        sc.at["FI", "unemployment_rate_15_74"], "% of labour force", QUARTER, "Eurostat une_rt_q")
    add("eu_ur_q", "EU27 unemployment rate, 15-74 (quarterly, seasonally adjusted)",
        sc.at[EU, "unemployment_rate_15_74"], "% of labour force", QUARTER, "Eurostat une_rt_q")

    # N9: youth unemployment rate (under 25), release series
    yur = headline_series(m, "Y_LT25", MONTH)

    # N10-N12: students and the denominator effect (annual)
    pg = d["lfsa_pganws"].pivot_table(index="geo", columns="wstatus", values="value")
    une_neet = d["edat_lfse_20"].set_index("geo")["value"]
    e18 = d["edat_lfse_18"].pivot_table(index="geo", columns="training", values="value")
    st = pd.DataFrame(index=list(NORDIC))
    st.index.name = "geo"
    st["population_15_24_ths"] = pg["POP"]
    st["labour_force_15_24_ths"] = pg["ACT"]
    st["employed_15_24_ths"] = pg["EMP"]
    st["unemployed_15_24_ths"] = pg["UNE"]
    st["unemployment_rate_pc_of_labour_force"] = 100 * pg["UNE"] / pg["ACT"]
    st["unemployment_ratio_pc_of_population"] = 100 * pg["UNE"] / pg["POP"]          # N10
    st["unemployed_not_in_education_pc_of_population"] = une_neet                     # edat_lfse_20
    st["unemployed_in_education_pc_of_population"] = (
        st["unemployment_ratio_pc_of_population"] - une_neet)
    st["share_of_unemployed_in_education_pc"] = 100 * (
        1 - une_neet / st["unemployment_ratio_pc_of_population"])                     # N11
    st["employed_in_education_pc_of_population"] = e18["FE_NFE"]                      # N12 (as specified)
    st["share_of_employed_in_education_pc"] = 100 * e18["FE_NFE"] / (
        e18["FE_NFE"] + e18["NO_FE_NO_NFE"])                                          # N12 (share of employed)
    st["year"] = YEAR
    st["name"] = [NORDIC[g][0] for g in st.index]

    # N13: Statistics Finland cross-check (13am), Finland 15-24
    a = d["13am"].set_index("contentscode")["value"]
    sf = {"population_15_24_ths": a["tyti-Vaesto"], "employed_15_24_ths": a["tyti-Tyolliset"],
          "employed_in_education_ths": a["Tyolliset_opisk_laaja"],
          "non_employed_15_24_ths": a["Ei_tyoll"],
          "non_employed_in_education_ths": a["Eityolliset_opisk_laaja"]}
    sf["share_of_non_employed_in_education_pc"] = 100 * sf["non_employed_in_education_ths"] / sf["non_employed_15_24_ths"]
    sf["share_of_employed_in_education_pc"] = 100 * sf["employed_in_education_ths"] / sf["employed_15_24_ths"]

    # N14: Finland's path since 2015 (Eurostat trend) and the StatFin cross-check
    fi_tc = pick(m, geo="FI", age="TOTAL", s_adj="TC").set_index("time")["value"].sort_index()
    lo, hi = fi_tc.min(), fi_tc.max()
    lo_m = list(fi_tc[fi_tc == lo].index)
    hi_m = list(fi_tc[fi_tc == hi].index)
    prev_year = (pd.Period(MONTH, "M") - 12).strftime("%Y-%m")
    add("fi_ur_change_12m", f"Finland unemployment rate change, {prev_year} to {MONTH} (trend)",
        round(fi_tc[MONTH] - fi_tc[prev_year], 1), "percentage points", f"{prev_year} to {MONTH}",
        "Eurostat une_rt_m, s_adj=TC")
    add("fi_ur_change_since_2025_01", f"Finland unemployment rate change, 2025-01 to {MONTH} (trend)",
        round(fi_tc[MONTH] - fi_tc["2025-01"], 1), "percentage points", f"2025-01 to {MONTH}",
        "Eurostat une_rt_m, s_adj=TC")
    add("fi_ur_low", f"Finland unemployment rate low since {START_MONTH} (trend)", lo,
        "% of labour force", ", ".join(lo_m), "Eurostat une_rt_m, s_adj=TC")
    add("fi_ur_high", f"Finland unemployment rate high since {START_MONTH} (trend)", hi,
        "% of labour force", ", ".join(hi_m), "Eurostat une_rt_m, s_adj=TC")

    z = d["135z"].pivot_table(index="timeperiod_m", columns="contentscode", values="value")
    z.index = [f"{t[:4]}-{t[5:]}" for t in z.index]
    zm = z.loc[MONTH]
    add("statfin_fi_ur_trend", "Statistics Finland unemployment rate, 15-74 (trend)",
        zm["tyottaste_trendi"], "% of labour force", MONTH, "StatFin 135z")
    add("statfin_fi_ur_sa", "Statistics Finland unemployment rate, 15-74 (seasonally adjusted)",
        zm["Tyottaste_kausi"], "% of labour force", MONTH, "StatFin 135z")
    add("statfin_fi_er_20_64_trend", "Statistics Finland employment rate, 20-64 (trend)",
        zm["Tyollaste_20_64_trendi"], "% of population", MONTH, "StatFin 135z")
    add("statfin_fi_er_20_64_sa", "Statistics Finland employment rate, 20-64 (seasonally adjusted)",
        zm["Tyollaste_20_64_kausi"], "% of population", MONTH, "StatFin 135z")
    fi_sa = pick(m, geo="FI", age="TOTAL", s_adj="SA").set_index("time")["value"]
    check = pd.DataFrame({"eurostat_trend": fi_tc, "statfin_trend": z["tyottaste_trendi"],
                          "eurostat_sa": fi_sa, "statfin_sa": z["Tyottaste_kausi"],
                          "statfin_unadjusted": z["tyti-Tyottomyysaste"]})
    check.index.name = "month"
    check["trend_diff_pp"] = check["eurostat_trend"] - check["statfin_trend"]
    check["sa_diff_pp"] = check["eurostat_sa"] - check["statfin_sa"]

    # T1: Nordic comparison table
    t1 = pd.DataFrame(index=list(NORDIC))
    t1.index.name = "geo"
    t1["name"] = [NORDIC[g][0] for g in t1.index]
    t1[f"unemployment_rate_{MONTH}"] = ur.reindex(t1.index)
    t1["unemployment_series"] = ["TC" if g in TC_GEOS else "SA" for g in t1.index]
    t1[f"employment_rate_20_64_{QUARTER}"] = sc["employment_rate_20_64"].reindex(t1.index)
    t1[f"activity_rate_20_64_{QUARTER}"] = sc["activity_rate_20_64"].reindex(t1.index)
    t1[f"youth_unemployment_rate_lt25_{MONTH}"] = yur.reindex(t1.index)
    t1[f"share_of_unemployed_15_24_in_education_{YEAR}"] = st["share_of_unemployed_in_education_pc"]

    # C2 data: monthly SA lines (plus the Finnish trend series)
    lines = pick(m, geo=list(NORDIC), age="TOTAL", s_adj="SA").pivot_table(
        index="time", columns="geo", values="value")[list(NORDIC)]
    lines["FI_trend"] = fi_tc
    lines.index.name = "month"

    # C3 data: employment and activity rates over time, FI and EU
    ea = pick(eq, geo=["FI", EU]).pivot_table(index="time", columns=["geo", "indic_em"], values="value")
    ea.columns = [f"{g}_{'employment' if i == 'EMP_LFS' else 'activity'}_rate_20_64" for g, i in ea.columns]
    ea.index.name = "quarter"

    # Write outputs
    OUT_DIR.mkdir(exist_ok=True)
    pd.DataFrame(head, dtype=object).to_csv(OUT_DIR / "headline.csv", index=False)
    scn = sc.copy()
    scn["highlight"] = scn.index == "FI"
    scn["period"] = QUARTER
    scn.to_csv(OUT_DIR / "scatter.csv", float_format="%.1f")
    st.to_csv(OUT_DIR / "students.csv", float_format="%.2f")
    pd.Series(sf, name=f"FI_{YEAR}").to_csv(OUT_DIR / "students_statfin_check.csv", float_format="%.2f",
                                            header=True)
    t1.to_csv(OUT_DIR / "t1_nordic.csv", float_format="%.1f")
    write_t1_md(t1, OUT_DIR / "t1_nordic.md")
    lines.to_csv(OUT_DIR / "c2_lines.csv", float_format="%.1f")
    ea.to_csv(OUT_DIR / "c3_employment_activity.csv", float_format="%.1f")
    check.to_csv(OUT_DIR / "fi_eurostat_vs_statfin.csv", float_format="%.1f")
    # Every downloaded Eurostat value that carries a flag (b = break in series, d = definition
    # differs, u = low reliability, p = provisional, e = estimated).
    flagged = pd.concat([df.loc[df["flag"] != ""].assign(dataset=code)
                         for code, df in d.items() if code[0].isalpha()], ignore_index=True)
    flagged.to_csv(OUT_DIR / "eurostat_flags.csv", index=False)
    ur.rename("unemployment_rate").to_frame().assign(
        series=["TC" if g in TC_GEOS else "SA" for g in ur.index],
        rank=rank.reindex(ur.index), period=MONTH).rename_axis("geo").to_csv(
        OUT_DIR / "eu_ranking_unemployment.csv", float_format="%.1f")

    return {"head": pd.DataFrame(head, dtype=object).set_index("id"), "sc": sc, "corr": corr,
            "both": both, "slope": slope, "icept": icept,
            "st": st, "sf": sf, "t1": t1, "lines": lines, "ea": ea, "check": check,
            "missing_m": missing_m, "ur": ur, "rank": rank, "flagged": flagged}


def write_t1_md(t1: pd.DataFrame, path: Path):
    cols = [("name", "Area", "{}"),
            (f"unemployment_rate_{MONTH}", f"Unemployment rate, {MONTH} (%)", "{:.1f}"),
            (f"employment_rate_20_64_{QUARTER}", f"Employment rate 20-64, {QUARTER} (%)", "{:.1f}"),
            (f"activity_rate_20_64_{QUARTER}", f"Activity rate 20-64, {QUARTER} (%)", "{:.1f}"),
            (f"youth_unemployment_rate_lt25_{MONTH}", f"Youth unemployment rate <25, {MONTH} (%)", "{:.1f}"),
            (f"share_of_unemployed_15_24_in_education_{YEAR}",
             f"Unemployed 15-24 in education or training, {YEAR} (% of unemployed)", "{:.0f}")]
    lines = ["| " + " | ".join(h for _, h, _ in cols) + " |",
             "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    for _, row in t1.iterrows():
        lines.append("| " + " | ".join(f.format(row[c]) if pd.notna(row[c]) else "n/a"
                                       for c, _, f in cols) + " |")
    lines += ["",
              "Unemployment rates: ages 15-74, trend series for Finland and Sweden, seasonally adjusted "
              "for Denmark and the EU (as in Eurostat's monthly release). Employment and activity "
              "rates: seasonally adjusted. Share of unemployed in education: annual, derived as "
              "1 - (unemployed and not in education, edat_lfse_20) / (unemployed / population, "
              "lfsa_pganws).",
              "",
              "Sources: Eurostat une_rt_m, lfsi_emp_q, lfsa_pganws, edat_lfse_20."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report(r: dict):
    h = r["head"]
    v = lambda k: h.at[k, "value"]
    print(f"\n=== Headline ({MONTH}, Eurostat une_rt_m) ===")
    print(f"N1  Finland unemployment rate (trend):   {v('fi_ur'):.1f}%  "
          f"[release: {RELEASE_FI_UR}%: {'matches' if abs(v('fi_ur') - RELEASE_FI_UR) < 0.05 else 'DIFFERS'}]")
    print(f"N2  EU27 unemployment rate (SA):         {v('eu_ur'):.1f}%  "
          f"[release: {RELEASE_EU_UR}%: {'matches' if abs(v('eu_ur') - RELEASE_EU_UR) < 0.05 else 'DIFFERS'}]")
    print(f"N3  Finland's rank (1 = highest):        {int(v('fi_rank_ur'))} of {int(r['rank'].count())}"
          + (f"  (no {MONTH} value for: {', '.join(r['missing_m'])})" if r["missing_m"] else ""))
    top = r["ur"].drop(EU).sort_values(ascending=False).head(5)
    print("    Top five: " + ", ".join(f"{g} {x:.1f}%" for g, x in top.items()))
    print(f"\n=== Employment ({QUARTER}, Eurostat lfsi_emp_q, ages 20-64, SA) ===")
    print(f"N4  Finland employment rate:             {v('fi_er'):.1f}%")
    print(f"N5  EU27 employment rate:                {v('eu_er'):.1f}%")
    print(f"N6  Finland's employment-rate rank:      {int(v('fi_rank_er'))} of {len(r['both'])}")
    print(f"N7  Pearson r (unemployment vs employment, {len(r['both'])} members): {r['corr']:.2f}; "
          f"Finland sits {v('fi_er_vs_fitted'):+.1f} pp from the fitted line")
    print("\n=== Nordic table T1 (also outputs/t1_nordic.md) ===")
    print(r["t1"].drop(columns=["unemployment_series"]).to_string(float_format=lambda x: f"{x:.1f}"))
    print(f"\n=== Young people 15-24, {YEAR} (Eurostat lfsa_pganws, edat_lfse_20, edat_lfse_18) ===")
    st = r["st"]
    for g, row in st.iterrows():
        print(f"  {row['name']:<8} rate {row['unemployment_rate_pc_of_labour_force']:5.1f}%  "
              f"ratio {row['unemployment_ratio_pc_of_population']:5.1f}% (N10)  "
              f"unemployed in education {row['share_of_unemployed_in_education_pc']:4.0f}% (N11)  "
              f"employed in education {row['share_of_employed_in_education_pc']:4.0f}% of employed / "
              f"{row['employed_in_education_pc_of_population']:.1f}% of population (N12)")
    sf = r["sf"]
    print(f"N13 StatFin 13am, Finland {YEAR}: {sf['share_of_non_employed_in_education_pc']:.0f}% of "
          f"non-employed 15-24 are in education or training "
          f"({sf['non_employed_in_education_ths']:.0f}k of {sf['non_employed_15_24_ths']:.0f}k); "
          f"{sf['share_of_employed_in_education_pc']:.0f}% of employed 15-24 are")
    print(f"\n=== Finland since {START_MONTH} (N14) ===")
    print(f"  Change over 12 months: {v('fi_ur_change_12m'):+.1f} pp; since 2025-01: "
          f"{v('fi_ur_change_since_2025_01'):+.1f} pp")
    print(f"  Low  {v('fi_ur_low'):.1f}% ({h.at['fi_ur_low', 'period']})")
    print(f"  High {v('fi_ur_high'):.1f}% ({h.at['fi_ur_high', 'period']})")
    c = r["check"].loc[MONTH]
    print(f"  {MONTH}: Eurostat trend {c['eurostat_trend']:.1f}% vs StatFin trend {c['statfin_trend']:.1f}%; "
          f"Eurostat SA {c['eurostat_sa']:.1f}% vs StatFin SA {c['statfin_sa']:.1f}%; "
          f"StatFin unadjusted {c['statfin_unadjusted']:.1f}%")
    print(f"  StatFin employment rate 20-64: trend {v('statfin_fi_er_20_64_trend'):.1f}%, "
          f"SA {v('statfin_fi_er_20_64_sa'):.1f}%")
    fl = r["flagged"]
    print(f"\nFlagged Eurostat values downloaded: {len(fl)} (see outputs/eurostat_flags.csv): "
          + ", ".join(f"{k} x{n}" for k, n in fl.groupby("flag").size().items()))


# --------------------------------------------------------------------------- #
# Step 3: charts (same style as kenya-remittance-costs)
# --------------------------------------------------------------------------- #
def style():
    plt.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 300, "font.size": 10.5,
        "font.family": "DejaVu Sans", "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.labelsize": 10.5, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.6,
        "legend.frameon": False, "legend.fontsize": 9.5, "svg.fonttype": "none"})


def finish(fig, ax, path: Path, source: str, note: str = "", offset: int = -30):
    text = (note + "\n" if note else "") + source
    ax.annotate(text, xy=(0, 0), xycoords="axes fraction", xytext=(-40, offset),
                textcoords="offset points", ha="left", va="top", fontsize=8, color="#555555",
                linespacing=1.4)
    fig.savefig(path.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def chart_scatter(r: dict, path: Path):
    sc, both = r["sc"], r["both"]
    x, y = both["unemployment_rate_15_74"], both["employment_rate_20_64"]
    fig, ax = plt.subplots(figsize=(10, 6.6))
    ax.scatter(x.drop("FI"), y.drop("FI"), s=38, color="#1f77b4", alpha=0.85, zorder=3)
    ax.scatter([x["FI"]], [y["FI"]], s=90, color="#c0392b", zorder=4)
    # Least-squares line across the EU members, to show the usual pattern.
    a, b = r["icept"], r["slope"]
    xs = pd.Series([x.min() - 0.3, x.max() + 0.3])
    ax.plot(xs, a + b * xs, color="#999999", lw=1.0, ls="-", zorder=1,
            label=f"Fitted line, EU members (r = {r['corr']:.2f})")
    eu_x, eu_y = sc.at[EU, "unemployment_rate_15_74"], sc.at[EU, "employment_rate_20_64"]
    ax.axvline(eu_x, color="#333333", ls="--", lw=0.9, zorder=1)
    ax.axhline(eu_y, color="#333333", ls="--", lw=0.9, zorder=1,
               label=f"EU27 average ({eu_x:.1f}%, {eu_y:.1f}%)")
    nudge = {"FI": (0, 9), "SE": (6, 4), "ES": (-6, 4), "EL": (6, -8)}
    for g in both.index:
        dx, dy = nudge.get(g, (5, 3))
        is_fi = g == "FI"
        ax.annotate("Finland" if is_fi else g, xy=(x[g], y[g]), xytext=(dx, dy),
                    textcoords="offset points", fontsize=10 if is_fi else 8.5,
                    fontweight="bold" if is_fi else "normal",
                    color="#c0392b" if is_fi else "#333333",
                    ha="center" if dx == 0 else ("right" if dx < 0 else "left"))
    ax.set_xlim(x.min() - 0.6, x.max() + 0.8)
    ax.set_xlabel("Unemployment rate, ages 15-74 (% of labour force)")
    ax.set_ylabel("Employment rate, ages 20-64 (% of population)")
    ax.set_title(f"Unemployment rate vs employment rate, EU members, {QUARTER.replace('-', ' ')}",
                 loc="left")
    ax.legend(loc="lower left")
    finish(fig, ax, path, SRC_ES.format("une_rt_q, lfsi_emp_q; seasonally adjusted"),
           note="Country codes: Eurostat (EL = Greece). Both rates seasonally adjusted, quarterly.",
           offset=-36)


def chart_lines(r: dict, path: Path):
    lines = r["lines"].copy()
    lines.index = pd.PeriodIndex(lines.index, freq="M").to_timestamp()
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ends = []
    for g, (lab, col) in NORDIC.items():
        s = lines[g].dropna()
        ax.plot(s.index, s.values, color=col, lw=2.2 if g == "FI" else 1.6, label=lab, zorder=3)
        ends.append([s.values[-1], s.index[-1], f"{lab} {s.values[-1]:.1f}%", col])
    s = lines["FI_trend"].dropna()
    ax.plot(s.index, s.values, color=NORDIC["FI"][1], lw=1.2, ls=(0, (3, 2)), zorder=2,
            label="Finland, trend series (Eurostat's headline for Finland)")
    ends.append([s.values[-1], s.index[-1], f"trend {s.values[-1]:.1f}%", NORDIC["FI"][1]])
    # Spread the end labels so they do not overlap.
    ends.sort(key=lambda e: e[0])
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 0.45)
    for yv, xv, txt, col in ends:
        ax.annotate(txt, xy=(xv, yv), xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=8.5, color=col, fontweight="bold", annotation_clip=False)
    ax.set_ylim(0, max(12.5, lines.max().max() + 1))
    ax.set_ylabel("Unemployment rate, ages 15-74 (% of labour force)")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(lines.index[0], lines.index[-1] + pd.Timedelta(days=20))
    ax.legend(loc="lower left", ncol=3)
    first = pd.Period(START_MONTH, "M").strftime("%b %Y")
    last = pd.Period(MONTH, "M").strftime("%b %Y")
    ax.set_title(f"Unemployment rate: Finland, Sweden, Denmark and the EU, {first} to {last}",
                 loc="left")
    finish(fig, ax, path, SRC_ES.format("une_rt_m"),
           note="Solid lines: seasonally adjusted. Eurostat's monthly release uses the trend series "
                "for Finland and Sweden (Sweden's trend not shown).")


def chart_employment_activity(r: dict, path: Path):
    ea = r["ea"].copy()
    ea.index = pd.PeriodIndex(ea.index.str.replace("-", ""), freq="Q").to_timestamp(how="start") \
        + pd.Timedelta(days=45)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6), sharey=True)
    for ax, (g, title) in zip(axes, [("FI", "Finland"), (EU, "EU27")]):
        act, emp = ea[f"{g}_activity_rate_20_64"], ea[f"{g}_employment_rate_20_64"]
        ax.fill_between(ea.index, emp, act, color="#f4c7c3", lw=0, label="Unemployed (gap)")
        ax.plot(ea.index, act, color="#555555", lw=1.6, label="Activity rate (in the labour force)")
        ax.plot(ea.index, emp, color="#1f77b4", lw=2.2, label="Employment rate")
        for s, col in ((act, "#555555"), (emp, "#1f77b4")):
            ax.annotate(f"{s.iloc[-1]:.1f}%", xy=(s.index[-1], s.iloc[-1]), xytext=(5, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=col,
                        fontweight="bold", annotation_clip=False)
        gap = act.iloc[-1] - emp.iloc[-1]
        ax.annotate(f"gap {gap:.1f} pp", xy=(act.index[-1], (act.iloc[-1] + emp.iloc[-1]) / 2),
                    xytext=(5, 0), textcoords="offset points", va="center", fontsize=8,
                    color="#c0392b", annotation_clip=False)
        ax.set_title(title, loc="left", fontsize=11.5)
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[0].set_ylim(64, 88)
    axes[0].set_ylabel("% of population aged 20-64")
    axes[0].legend(loc="lower left", fontsize=8.5)
    fig.suptitle(f"Activity and employment rates, ages 20-64: Finland and the EU "
                 f"({START_QUARTER.replace('-', ' ')} to {QUARTER.replace('-', ' ')})",
                 x=0.075, ha="left", fontsize=13, fontweight="bold")
    fig.subplots_adjust(wspace=0.18)
    finish(fig, axes[0], path, SRC_ES.format("lfsi_emp_q; seasonally adjusted, quarterly"),
           note="Ages 20-64. The shaded gap is unemployed people as a share of the whole population "
                "aged 20-64, not the unemployment rate. Y-axis starts at 64%.")


def chart_youth(r: dict, path: Path):
    st = r["st"].loc[list(NORDIC)[::-1]]
    series = [("unemployment_rate_pc_of_labour_force", "Unemployment rate (% of labour force)", "#c0392b"),
              ("unemployment_ratio_pc_of_population", "Unemployed, % of all aged 15-24", "#e8a09a"),
              ("unemployed_not_in_education_pc_of_population",
               "Unemployed and not in education or training, % of all aged 15-24", "#7f7f7f")]
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.grid(axis="y", visible=False)
    h = 0.26
    ys = range(len(st))
    for k, (col, lab, colour) in enumerate(series):
        pos = [y + (1 - k) * h for y in ys]
        ax.barh(pos, st[col], height=h * 0.92, color=colour, label=lab, zorder=2)
        for p, val in zip(pos, st[col]):
            ax.annotate(f"{val:.1f}%", xy=(val, p), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=8.5, color="#333333")
    ax.set_yticks(list(ys), [NORDIC[g][0] for g in st.index])
    ax.set_xlim(0, max(25, st[series[0][0]].max() + 3))
    ax.set_xlabel(f"Young people aged 15-24, {YEAR} (%)")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title(f"Young people: the same unemployed, three denominators ({YEAR})", loc="left")
    finish(fig, ax, path, SRC_ES.format("lfsa_pganws, edat_lfse_20; annual"),
           note="Students who look for work and could start count as unemployed. "
                "The gap between the pink and grey bars is unemployed people in education or training.", offset=-36)


def charts(r: dict):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    style()
    chart_scatter(r, CHART_DIR / "c1_scatter")
    chart_lines(r, CHART_DIR / "c2_lines")
    chart_employment_activity(r, CHART_DIR / "c3_employment_activity")
    chart_youth(r, CHART_DIR / "c4_youth_denominators")
    print(f"\nCharts and CSVs written to {OUT_DIR}")


# --------------------------------------------------------------------------- #
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    refresh = "--refresh" in sys.argv
    data = download(refresh)
    results = analyse(data)
    report(results)
    charts(results)


if __name__ == "__main__":
    main()
