# Finland tops the EU jobless table. Is it as bad as it looks?

Code to reproduce the numbers, the comparison table and the charts for Elly Okinyo's article on Finland's unemployment rate and employment rate (October 2026, draft; not yet published).

Finland has the highest unemployment rate in the EU, yet its employment rate is close to the EU average. The two rates use different denominators (the labour force against the whole population), and Finland has a large labour force share, including many students who look for work and count as unemployed. This repository fetches the public data behind that comparison.

The repository holds code only. No data files are committed: the script downloads the data from the Eurostat and Statistics Finland APIs each time it runs and caches the responses outside the project folder (see [Where things live](#where-things-live)). No API keys needed. The script needs only a plain folder copy of the repository (no git).

## What it reproduces

`unemployment_paradox.py` runs three steps:

1. **Download** eight small API queries (about 260 kB in total): six Eurostat datasets and two Statistics Finland (StatFin) Labour Force Survey tables.
2. **Analyse** and print every number the article needs:
   - N1-N3: Finland's and the EU's unemployment rate for August 2026 and Finland's rank among the 27 EU members (using the series Eurostat's monthly release uses: trend for Germany, the Netherlands, Finland and Sweden, seasonally adjusted for the rest), checked against the release (10.3% and 6.1%)
   - N4-N7: employment rate 20-64 for Finland and the EU in 2026 Q2, Finland's rank, and the correlation between unemployment and employment rates across the EU (plus Finland's distance from the fitted line)
   - N8-N12: activity rates, youth unemployment rates, the youth unemployment ratio, and the shares of unemployed and employed young people who are in education or training (Finland, Sweden, Denmark, EU)
   - N13: the same student split from Statistics Finland's own table, as a cross-check
   - N14: Finland's unemployment rate since January 2015 (change, low, high), with Eurostat's and Statistics Finland's trend and seasonally adjusted series side by side
   - T1: the Nordic comparison table
3. **Chart** four figures.

## Where things live

- **Code:** this repo. The project folder needs only the scripts, this README, `requirements.txt`, `clean.ps1` and `LICENSE`; the run adds `outputs/`.
- **Virtual environment:** `%LOCALAPPDATA%\venvs\finland-unemployment-paradox`, outside the project folder. If you keep the project in a cloud-synced folder, keep `.git`, the venv and the data cache out of it: sync can corrupt git and small-file trees.
- **Download cache:** `%LOCALAPPDATA%\project-data\finland-unemployment-paradox\raw\` (on macOS/Linux `~/.cache/project-data/finland-unemployment-paradox/raw/`; set `FUP_DATA_DIR` to override).

## Run (Windows PowerShell)

Requires Python 3.11 or newer (the `py` launcher). From the project folder:

    cd path\to\finland-unemployment-paradox
    py -m venv $env:LOCALAPPDATA\venvs\finland-unemployment-paradox
    & $env:LOCALAPPDATA\venvs\finland-unemployment-paradox\Scripts\python -m pip install -r requirements.txt
    & $env:LOCALAPPDATA\venvs\finland-unemployment-paradox\Scripts\python unemployment_paradox.py
    .\clean.ps1

Delete the venv after the run to save space: the last line removes it and the download cache (see [Clean up](#clean-up-after-a-run)). To rebuild the venv in one line: `py -m venv $env:LOCALAPPDATA\venvs\finland-unemployment-paradox; & $env:LOCALAPPDATA\venvs\finland-unemployment-paradox\Scripts\pip install -r requirements.txt`

A run downloads eight small API responses (well under 1 MB) and takes under a minute. If the cache is still there, later runs reuse it and take a few seconds; add `--refresh` to download again.

## Run (macOS / Linux)

    cd path/to/finland-unemployment-paradox
    python3 -m venv ~/.cache/venvs/finland-unemployment-paradox
    ~/.cache/venvs/finland-unemployment-paradox/bin/python -m pip install -r requirements.txt
    ~/.cache/venvs/finland-unemployment-paradox/bin/python unemployment_paradox.py
    rm -rf ~/.cache/venvs/finland-unemployment-paradox ~/.cache/project-data/finland-unemployment-paradox

## Outputs (created next to the script)

Charts (300 dpi PNG plus SVG) in `outputs/charts/`:

- `c1_scatter.png` (Chart C1): unemployment rate (15-74) against employment rate (20-64), all 27 EU members, 2026 Q2, with Finland highlighted, EU averages as reference lines and a fitted line
- `c2_lines.png` (Chart C2): unemployment rate, Finland, Sweden, Denmark and the EU, January 2015 to August 2026 (seasonally adjusted, with Finland's trend series dashed)
- `c3_employment_activity.png`: activity rate and employment rate (20-64), Finland and the EU, 2015 Q1 to 2026 Q2; the shaded gap is the unemployed as a share of the population
- `c4_youth_denominators.png`: young people aged 15-24 in 2025: unemployment rate, unemployment ratio, and unemployed and not in education, for Finland, Sweden, Denmark and the EU

Tables in `outputs/`:

- `headline.csv`: every headline number (N1-N8, N14 and the StatFin cross-checks), one row each, with unit, period and source
- `scatter.csv`: the data behind C1 (27 members and the EU)
- `eu_ranking_unemployment.csv`: unemployment rate and rank for all 27 members, August 2026
- `t1_nordic.csv` and `t1_nordic.md`: Table T1
- `students.csv`: N9-N12 for Finland, Sweden, Denmark and the EU; `students_statfin_check.csv`: N13
- `c2_lines.csv`, `c3_employment_activity.csv`: the data behind C2 and C3
- `fi_eurostat_vs_statfin.csv`: Finland's monthly unemployment rate in both sources, trend and seasonally adjusted, with differences
- `eurostat_flags.csv`: every downloaded Eurostat value that carries a flag (break in series, definition differs, low reliability)

Outputs are never committed.

Every chart's footer reads "Source: Eurostat (dataset codes); author's calculations."

## Clean up (after a run)

`clean.ps1` frees disk space after a run. It deletes the venv (`%LOCALAPPDATA%\venvs\finland-unemployment-paradox`), the download cache (`%LOCALAPPDATA%\project-data\finland-unemployment-paradox`) and any `.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.ipynb_checkpoints` or `data/` inside the project folder. It keeps `outputs/` and never touches files tracked by git. It prints the MB freed and is safe to rerun. From the project folder in PowerShell:

    .\clean.ps1

(Add `-DryRun` to see what would be removed without deleting anything. If script execution is blocked, use `powershell -ExecutionPolicy Bypass -File .\clean.ps1`.)

## Method notes

- **Two rates, two denominators.** The unemployment rate is the unemployed (ILO definition: no work, looked for work in the past four weeks, can start within two weeks) as a share of the labour force aged 15-74. The employment rate is the employed as a share of the whole population aged 20-64. The activity rate is the labour force as a share of the population.
- **Trend or seasonally adjusted.** For Germany, the Netherlands, Finland and Sweden, Eurostat's monthly release uses "the trend component ... instead of the more volatile seasonally adjusted data" (country notes, release of 1 October 2026). N1, N3, N9 and T1 follow the release. Chart C2 shows seasonally adjusted lines for all four areas so that they are comparable, and adds Finland's trend series as a dashed line (August 2026: trend 10.3%, seasonally adjusted 9.9%).
- **Eurostat and Statistics Finland differ slightly.** Both publish Finland's LFS unemployment rate, ages 15-74. The seasonally adjusted series agree for August 2026 (9.9% in both), but the trend series do not (Eurostat 10.3%, Statistics Finland 10.1%). Since 2021 the trend series differ by up to 0.3 points in a month and the seasonally adjusted series by up to 0.2 points. The script records both in `fi_eurostat_vs_statfin.csv`; it does not explain the difference. The two agencies run their own seasonal and trend adjustment, and the latest months of any trend are revised as new data arrive. Confirm the reason with Eurostat or Statistics Finland before stating one.
- **Students.** Students who look for work and can start count as unemployed. N11 (the share of unemployed 15-24 year-olds who are in education or training) is derived as 1 − (unemployed and not in education, `edat_lfse_20`, % of population) ÷ (unemployed ÷ population, `lfsa_pganws`). "Education or training" includes non-formal training. Statistics Finland's table 13am has no split of the unemployed, so N13 uses its non-employed split as a cross-check (a different, wider group).
- **N12.** `edat_lfse_18` gives the employed in education as a share of the *whole* population aged 15-24 (for example Finland 26.7% in 2025). The script reports that value and also the share of the *employed* who are in education (26.7 ÷ (26.7 + 15.1) = 64%).
- **Fitted line in C1.** An ordinary least-squares line across the 27 members, for orientation only; it is not a model.
- **Reference periods are pinned** at the top of the script (`MONTH = "2026-08"`, `QUARTER = "2026-Q2"`, `YEAR = "2025"`), so the numbers do not move when newer data come out. Revisions to those periods can still change them. To update, change the constants and run with `--refresh`.

## Caveats

- The LFS is a sample survey. Statistics Finland puts the margin of error of the number of unemployed in August 2026 at ±23,000 people (262,000 unemployed; [release of 22 September 2026](https://stat.fi/en/publication/cmfp96le0a4mm07vyv0oyqv4n)). The latest months of any trend series are revised as new months arrive: Eurostat revised Finland's July 2026 rate down by 0.2 points in its 1 October release.
- In Eurostat's monthly release, Estonia and Portugal are 3-month moving averages, and when a country's latest month is missing the EU aggregate uses its latest available data.
- Series breaks: the EU LFS was revised in 2021 (new regulation); Statistics Finland's table 135z has been back-cast to the new method, but Eurostat flags breaks for Sweden (July 2018) and Denmark (October 2023 / 2023 Q4 and the 2025 youth data). Eurostat flags "definition differs" for France and Spain in the quarterly data. All flagged values downloaded are listed in `outputs/eurostat_flags.csv`.
- Annual youth data (2025) and quarterly employment data (2026 Q2) are older than the monthly unemployment data (August 2026); every output labels its own period.
- Populations differ between sources: Eurostat's `lfsa_pganws` covers people in private households (Finland, 15-24, 2025: 616,000), while Statistics Finland's table 13am shows 636,000. Use each source's shares, not its levels, side by side.
- The ages differ: 15-74 for unemployment, 20-64 for employment and activity rates, under 25 or 15-24 for young people.

## If the download fails

Run the script again (it retries three times). If an API is down, the same data can be viewed in a browser through the links below; the script itself needs the APIs.

## Data sources

All accessed 7 October 2026. Eurostat API base: <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/>. StatFin API base: <https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/tyti/>.

- Eurostat `une_rt_m`, Unemployment by sex and age, monthly data (sex=T, age=TOTAL and Y_LT25, unit=PC_ACT, s_adj=SA and TC): <https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table>
- Eurostat `une_rt_q`, Unemployment by sex and age, quarterly data (age=Y15-74, unit=PC_ACT, s_adj=SA): <https://ec.europa.eu/eurostat/databrowser/view/une_rt_q/default/table>
- Eurostat `lfsi_emp_q`, Employment and labour force by sex and age, quarterly data (indic_em=EMP_LFS and ACT, age=Y20-64, unit=PC_POP, s_adj=SA): <https://ec.europa.eu/eurostat/databrowser/view/lfsi_emp_q/default/table>
- Eurostat `lfsa_pganws`, Population by citizenship and labour status, annual (age=Y15-24, citizen=TOTAL, unit=THS_PER): <https://ec.europa.eu/eurostat/databrowser/view/lfsa_pganws/default/table>
- Eurostat `edat_lfse_20`, Young people neither in employment nor in education and training by labour status (wstatus=UNE, training=NO_FE_NO_NFE, age=Y15-24): <https://ec.europa.eu/eurostat/databrowser/view/edat_lfse_20/default/table>
- Eurostat `edat_lfse_18`, Participation of young people in education and training by labour status (wstatus=EMP, age=Y15-24): <https://ec.europa.eu/eurostat/databrowser/view/edat_lfse_18/default/table>
- Statistics Finland, Labour Force Survey, release of 22 September 2026 (margin of error, trend figures): <https://stat.fi/en/publication/cmfp96le0a4mm07vyv0oyqv4n>
- Statistics Finland, Labour Force Survey, table 135z, key indicators with seasonally adjusted and trend series, monthly: <https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__tyti/statfin_tyti_pxt_135z.px/> (API: <https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/tyti/135z.px>)
- Statistics Finland, Labour Force Survey, table 13am, young people (15-29) in education and the labour market, annual: <https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__tyti/statfin_tyti_pxt_13am.px/> (API: <https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/tyti/13am.px>)
- Eurostat euro indicators release, 1 October 2026 (used as a check on N1 and N2, and for the trend-series and revision notes): <https://ec.europa.eu/eurostat/web/products-euro-indicators/w/3-01102026-ap>

## License

MIT, see [LICENSE](LICENSE).
