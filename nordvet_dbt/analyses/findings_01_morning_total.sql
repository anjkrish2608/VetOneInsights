-- FINDINGS.md, morning view: network totals for the last open day.
with daily as (
    select * from {{ ref('mart_clinic_daily_noshows') }}
),

last_open_day as (
    select *
    from daily
    where is_last_open_day
)

select
    appointment_date,
    sum(appointments)                                                   as appointments,
    sum(completed)                                                      as completed,
    sum(no_shows)                                                       as no_shows,
    sum(cancelled)                                                      as cancelled,
    sum(awaiting_status)                                                as awaiting,
    round(100.0 * sum(no_shows) / sum(completed + no_shows), 1)         as rate_pct,
    round(100.0 * sum(no_shows + awaiting_status)
          / sum(completed + no_shows + awaiting_status), 1)             as upper_pct,
    sum(lost_vet_minutes)                                               as lost_minutes
from last_open_day
group by appointment_date
