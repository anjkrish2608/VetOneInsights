# Findings from Nordvet VetOne No Show Pipeline

**As of Monday 9 November 2026.** Data loaded from VetOne at 13:54 UTC (run `20261109T135405Z`). Covers 1 September to 7 November 2026, 38 active clinics. Numbers are frozen at this run; the pipeline produces a fresh view every morning.

## Key takeaway

 No-shows are steady at about 9% across Nordvet, but four Danish clinics run at twice that or more, and Odense C has got sharply worse in the last month.

---

## Your morning view: last open day (Saturday 7 November)

Clinics are closed on Sundays, so on a Monday "yesterday" means Saturday.

**Network: 292 appointments, 14 confirmed no-shows, 2 still awaiting status.** Confirmed rate 5.1% (5.8% if both awaiting turn out to be no-shows). 380 vet minutes lost.

The 5 clinics with the most no-shows:

| Clinic | Appointments | No-shows | Awaiting status | Rate | Vet minutes lost |
|---|---:|---:|---:|---:|---:|
| Stockholm Södermalm | 14 | 3 | 0 | 21.4% | 125 |
| København V | 11 | 2 | 0 | 20.0% | 65 |
| Göteborg Hisingen | 10 | 1 | 1 | 12.5% | 15 |
| Malmö Limhamn | 15 | 1 | 0 | 7.7% | 15 |
| Valby | 14 | 1 | 0 | 7.1% | 20 |

27 of 38 clinics had no no-shows on Saturday. All clinics are in the table `mart_clinic_daily_noshows` (filter `is_last_open_day`).

**"Awaiting status"** = appointments in the past that are still marked *booked*. No-shows are typically recorded about a day late, so yesterday's count always grows over the next few days. Read the confirmed number as "at least", not "final".

---

## Findings

Rates below are over the **newest 28 settled days (6 Oct – 5 Nov)** unless stated. Days less than 3 days old are left out because their no-shows aren't all recorded yet.

1. **No-shows are concentrated in a few clinics.** The network rate is 8.8%. Four clinics run at more than twice that: Aarhus C (24.4%), Hillerød (24.3%), Odense C (22.6%) and København V (18.9%), all in Denmark. *We suggest* start with these four clinics, not a network-wide campaign.

   | | Clinic | Rate (28 days) | No-shows | Vet hours lost | Sep–Nov average |
   |---|---|---:|---:|---:|---:|
   | Worst | Aarhus C | 24.4% | 82 | 27.7 | 21.3% |
   | | Hillerød | 24.3% | 106 | 37.6 | 24.4% |
   | | Odense C | 22.6% | 79 | 25.2 | 14.8% |
   | Best | København Ø | 3.6% | 11 | 3.5 | 5.2% |
   | | Odense S | 3.2% | 15 | 5.5 | 4.0% |
   | | Næstved | 3.1% | 12 | 3.6 | 4.0% |

2. **Odense C is getting worse fast.** Up from 14.8% (its Sep–Nov average) to 22.6% in the last 28 days, +7.8 percentage points. Aarhus C is also rising (+3.1). Hillerød is high but stable. This implies something changed at Odense C recently.  *We suggest* it's worth making a call this week.

3. **Across the network nothing is getting worse.** The weekly rate has stayed between 7.7% and 9.5% every week since September. *We suggest* this is a problem at specific clinics, not a general decline.

4. **Routine visits are missed most.** Follow-ups 12.6%, vaccinations 11.4%, consultations 7.9%, dental 5.3%, surgery 2.5% (1 Sep – 5 Nov). *We suggest* reminders (SMS the day before) are most likely to pay off on routine visits.

5. **Mondays are worst.** Monday 10.5%; every other day 7.7–8.5% (1 Sep – 5 Nov). *We suggest* booking reminders for Monday are sent on the last working day to allow time for contact.

6. **The cost, in vet time.** 525 vet hours were lost to no-shows in the 28 days, about 131 hours a week: **the equivalent of about 3.5 full-time vets' booked time** (37-hour week). The 5 worst clinics account for 29% of it. *We suggest* incorporating vet hourly rates to look at this variable in a financial context.

7. **Denmark is slightly worse than Sweden.** DK 9.2%, SE 7.8%. The gap is mostly the four Danish clinics in finding 1.

---

## How to read these numbers

- **Yesterday is never complete at 8am.** Use the confirmed count plus "awaiting status".
- **Rankings use settled days only** (older than 3 days). By then almost every no-show is recorded: only 3 appointments on settled days are still awaiting a status.
- **Cancelled appointments are excluded** from the rate: no-shows ÷ (completed + no-shows).
- **Lost time is in vet minutes, not kroner**, because VetOne has no prices.

## Questions for Nordvet

1. **Are late cancellations really no-shows?** About 1 in 5 cancellations (743 of 3,519, 1 Sep – 5 Nov) is recorded *after* the appointment had started. These may be patients who didn't come. They are not counted as no-shows today. Should they be?
2. **What is the revenue per vet hour?** With it, lost time can be shown in kroner.
3. **The brief says 38 clinics; VetOne lists 39.** The 39th, Nordvet Ystad, is marked inactive with no appointments since September. Is it closed? It's left out of the ranking.

---

## Appendix: how to reproduce

All numbers come from `data/nordvet.duckdb` after `python run_pipeline.py`. To rebuild the marts as of this document's date:

```bash
.venv\Scripts\dbt build --project-dir nordvet_dbt --profiles-dir nordvet_dbt --vars "{as_of_date: '2026-11-09'}"
```

The data is live, so a later run can shift numbers slightly as statuses keep changing.

The SQL behind every number is a dbt analysis in [nordvet_dbt/analyses/](nordvet_dbt/analyses/). Analyses use `ref()` like the models, so dbt checks them when it compiles. Run one with `dbt show`, for example:

```bash
.venv\Scripts\dbt show --project-dir nordvet_dbt --profiles-dir nordvet_dbt --select findings_06_service
```

| Number in this document | Analysis |
|---|---|
| Morning view: network total | [findings_01_morning_total.sql](nordvet_dbt/analyses/findings_01_morning_total.sql) |
| Morning view: 5 clinics with the most no-shows | [findings_02_morning_top5.sql](nordvet_dbt/analyses/findings_02_morning_top5.sql) |
| Findings 1, 2: worst and best 3 | [findings_03_ranking_worst_best.sql](nordvet_dbt/analyses/findings_03_ranking_worst_best.sql) |
| Finding 1: clinics above twice the network rate | [findings_04_over_2x_network.sql](nordvet_dbt/analyses/findings_04_over_2x_network.sql) |
| Finding 3: weekly network rate | [findings_05_weekly_rate.sql](nordvet_dbt/analyses/findings_05_weekly_rate.sql) |
| Finding 4: rate by service | [findings_06_service.sql](nordvet_dbt/analyses/findings_06_service.sql) |
| Finding 5: rate by weekday | [findings_07_weekday.sql](nordvet_dbt/analyses/findings_07_weekday.sql) |
| Finding 6: lost vet hours and full-time vets | [findings_08_lost_hours.sql](nordvet_dbt/analyses/findings_08_lost_hours.sql) |
| Finding 6: the 5 worst clinics' share | [findings_09_lost_top5_share.sql](nordvet_dbt/analyses/findings_09_lost_top5_share.sql) |
| Finding 7: by country | [findings_10_country.sql](nordvet_dbt/analyses/findings_10_country.sql) |
| Question 1: cancellations after the start | [findings_11_late_cancellations.sql](nordvet_dbt/analyses/findings_11_late_cancellations.sql) |

Findings 4 and 5 (service and weekday) are analyses rather than marts for now. With more time they would get their own mart, so they are built and tested every run like the rest (see DECISIONS.md, Next steps).
