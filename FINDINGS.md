# No-show findings for Mette

**As of Monday 9 November 2026.** Data loaded from VetOne at 13:54 UTC (run `20261109T135405Z`).
Covers 1 September to 7 November 2026, 38 active clinics. Numbers are frozen at this run;
the pipeline produces a fresh view every morning.

**In one sentence:** no-shows are steady at about 9% across Nordvet, but four Danish clinics
run at twice that or more, and Odense C has got sharply worse in the last month.

---

## Your morning view: last open day (Saturday 7 November)

Clinics are closed on Sundays, so on a Monday "yesterday" means Saturday.

**Network: 292 appointments, 14 confirmed no-shows, 2 still awaiting status.**
Confirmed rate 5.1% (5.8% if both awaiting turn out to be no-shows). 380 vet minutes lost.

The 5 clinics with the most no-shows:

| Clinic | Appointments | No-shows | Awaiting status | Rate | Vet minutes lost |
|---|---:|---:|---:|---:|---:|
| Stockholm Södermalm | 14 | 3 | 0 | 21.4% | 125 |
| København V | 11 | 2 | 0 | 20.0% | 65 |
| Göteborg Hisingen | 10 | 1 | 1 | 12.5% | 15 |
| Malmö Limhamn | 15 | 1 | 0 | 7.7% | 15 |
| Valby | 14 | 1 | 0 | 7.1% | 20 |

27 of 38 clinics had no no-shows on Saturday. All clinics are in the table
`mart_clinic_daily_noshows` (filter `is_last_open_day`).

**"Awaiting status"** = appointments in the past that are still marked *booked*. No-shows are
typically recorded about a day late, so yesterday's count always grows over the next few days.
Read the confirmed number as "at least", not "final".

---

## Findings

Rates below are over the **newest 28 settled days (6 Oct – 5 Nov)** unless stated. Days
less than 3 days old are left out because their no-shows aren't all recorded yet.

1. **No-shows are concentrated in a few clinics.** The network rate is 8.8%. Four clinics run
   at more than twice that: Aarhus C (24.4%), Hillerød (24.3%), Odense C (22.6%) and
   København V (18.9%), all in Denmark.
   *So what:* start with these four clinics, not a network-wide campaign.

   | | Clinic | Rate (28 days) | No-shows | Vet hours lost | Sep–Nov average |
   |---|---|---:|---:|---:|---:|
   | Worst | Aarhus C | 24.4% | 82 | 27.7 | 21.3% |
   | | Hillerød | 24.3% | 106 | 37.6 | 24.4% |
   | | Odense C | 22.6% | 79 | 25.2 | 14.8% |
   | Best | København Ø | 3.6% | 11 | 3.5 | 5.2% |
   | | Odense S | 3.2% | 15 | 5.5 | 4.0% |
   | | Næstved | 3.1% | 12 | 3.6 | 4.0% |

2. **Odense C is getting worse fast.** Up from 14.8% (its Sep–Nov average) to 22.6% in the
   last 28 days, +7.8 percentage points. Aarhus C is also rising (+3.1). Hillerød is
   high but stable.
   *So what:* something changed at Odense C recently. Worth a call this week.

3. **Across the network nothing is getting worse.** The weekly rate has stayed between 7.7%
   and 9.5% every week since September.
   *So what:* this is a problem at specific clinics, not a general decline.

4. **Routine visits are missed most.** Follow-ups 12.6%, vaccinations 11.4%,
   consultations 7.9%, dental 5.3%, surgery 2.5% (1 Sep – 5 Nov).
   *So what:* reminders (SMS the day before) are most likely to pay off on routine visits.

5. **Mondays are worst.** Monday 10.5%; every other day 7.7–8.5% (1 Sep – 5 Nov).
   *So what:* weekend bookings for Monday are the ones to remind.

6. **The cost, in vet time.** 525 vet hours were lost to no-shows in the 28 days, about
   131 hours a week: **the equivalent of about 3.5 full-time vets' booked time**
   (37-hour week). The 5 worst clinics account for 29% of it.
   *So what (for Karin):* VetOne has no prices, so this is time, not kroner. Multiplying by
   Nordvet's revenue per vet hour turns it into money.

7. **Denmark is slightly worse than Sweden.** DK 9.2%, SE 7.8%. The gap is mostly the four
   Danish clinics in finding 1.

---

## How to read these numbers

- **Yesterday is never complete at 8am.** Use the confirmed count plus "awaiting status".
- **Rankings use settled days only** (older than 3 days). By then almost every no-show is
  recorded: only 3 appointments on settled days are still awaiting a status.
- **Cancelled appointments are excluded** from the rate: no-shows ÷ (completed + no-shows).
- **Lost time is in vet minutes, not kroner**, because VetOne has no prices.

## Questions for Nordvet

1. **Are late cancellations really no-shows?** About 1 in 5 cancellations (743 of 3,519,
   1 Sep – 5 Nov) is recorded *after* the appointment had started. These may be patients who
   didn't come. They are not counted as no-shows today. Should they be?
2. **What is the revenue per vet hour?** With it, lost time can be shown in kroner.
3. **The brief says 38 clinics; VetOne lists 39.** The 39th, Nordvet Ystad, is marked
   inactive with no appointments since September. Is it closed? It's left out of the ranking.

---

## Appendix: how to reproduce

All numbers come from the DuckDB file `data/nordvet.duckdb` after `python run_pipeline.py`.
To rebuild the marts as of this document's date:

```bash
.venv/Scripts/dbt build --project-dir nordvet_dbt --profiles-dir nordvet_dbt --vars "{as_of_date: '2026-11-09'}"
```

The data is live, so a later run can shift numbers slightly as statuses keep changing.
Run any query below in a DuckDB client (e.g. DBeaver), or from Python:
`duckdb.connect('data/nordvet.duckdb', read_only=True).sql("<query>").show()`

Findings 4 and 5 (service and weekday) are queried from staging and the daily mart here.
With more time they would get their own mart, so they are built and tested every run like
the rest (see DECISIONS.md, Next steps).

**Morning view: network total (last open day)**
```sql
select appointment_date, sum(appointments) as appointments, sum(completed) as completed,
       sum(no_shows) as no_shows, sum(cancelled) as cancelled, sum(awaiting_status) as awaiting,
       round(100.0 * sum(no_shows) / sum(completed + no_shows), 1) as rate_pct,
       round(100.0 * sum(no_shows + awaiting_status)
             / sum(completed + no_shows + awaiting_status), 1) as upper_pct,
       sum(lost_vet_minutes) as lost_minutes
from mart_clinic_daily_noshows
where is_last_open_day
group by appointment_date;
```

**Morning view: 5 clinics with the most no-shows**
```sql
select clinic_name, appointments, no_shows, awaiting_status,
       round(100 * no_show_rate, 1) as rate_pct, lost_vet_minutes
from mart_clinic_daily_noshows
where is_last_open_day
order by no_shows desc, awaiting_status desc, appointments desc
limit 5;
```

**Findings 1, 2: worst and best 3, and network totals**
```sql
select rank_recent, clinic_name, round(100 * no_show_rate_recent, 1) as recent_pct,
       no_shows_recent, lost_vet_hours_recent, round(100 * no_show_rate_history, 1) as history_pct
from mart_clinic_noshow_ranking
where rank_recent <= 3 or rank_recent > (select count(*) - 3 from mart_clinic_noshow_ranking)
order by rank_recent;

select clinic_name, round(100 * no_show_rate_recent, 1) as recent_pct
from mart_clinic_noshow_ranking
where no_show_rate_recent > 2 * network_rate_recent;
```

**Finding 3: weekly network rate (settled days)**
```sql
select date_trunc('week', appointment_date) as week_starting,
       round(100.0 * sum(no_shows) / sum(completed + no_shows), 1) as rate_pct
from mart_clinic_daily_noshows
where is_settled and is_active
group by 1 order by 1;
```

**Finding 4: rate by service (settled days, active clinics)**
```sql
select a.service,
       round(100.0 * sum(case when a.status = 'no_show' then 1 else 0 end)
             / sum(case when a.status in ('completed', 'no_show') then 1 else 0 end), 1) as rate_pct
from stg_vetone__appointments as a
join stg_vetone__clinics as c on a.clinic_id = c.clinic_id and c.is_active
where a.scheduled_date_local <= (select max(settled_until) from mart_clinic_noshow_ranking)
group by a.service
order by rate_pct desc;
```

**Finding 5: rate by weekday (settled days, active clinics)**
```sql
select dayname(appointment_date) as weekday,
       round(100.0 * sum(no_shows) / sum(completed + no_shows), 1) as rate_pct
from mart_clinic_daily_noshows
where is_settled and is_active
group by weekday, isodow(appointment_date)
order by isodow(appointment_date);
```

**Finding 6: lost vet hours, and the 5 worst clinics' share**
```sql
select round(sum(lost_vet_minutes_recent) / 60.0) as lost_hours_28d
from mart_clinic_noshow_ranking;
-- 525 h / 4 weeks = 131 h a week, and 131 h / 37 h full-time week = about 3.5 full-time vets

with ranked as (
    select lost_vet_minutes_recent,
           rank() over (order by lost_vet_minutes_recent desc) as r
    from mart_clinic_noshow_ranking
)
select round(100.0 * sum(case when r <= 5 then lost_vet_minutes_recent else 0 end)
             / sum(lost_vet_minutes_recent)) as top5_share_pct
from ranked;
```

**Finding 7: by country**
```sql
select country,
       round(100.0 * sum(no_shows_recent) / sum(completed_recent + no_shows_recent), 1) as recent_pct
from mart_clinic_noshow_ranking
group by country;
```

**Question 1: cancellations recorded after the appointment started**
```sql
select count(*) as cancelled,
       sum(case when cancelled_at > scheduled_at then 1 else 0 end) as after_start
from stg_vetone__appointments
where status = 'cancelled'
  and scheduled_date_local <= (select max(settled_until) from mart_clinic_noshow_ranking);
```
