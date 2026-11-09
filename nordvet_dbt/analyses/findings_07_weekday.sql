-- FINDINGS.md, finding 5: no-show rate by weekday, settled days, active clinics.
with daily as (
    select * from {{ ref('mart_clinic_daily_noshows') }}
)

select
    dayname(appointment_date)                                        as weekday,
    round(100.0 * sum(no_shows) / sum(completed + no_shows), 1)      as rate_pct,
    sum(completed + no_shows)                                        as attended_or_missed
from daily
where is_settled
  and is_active
group by weekday, isodow(appointment_date)
order by isodow(appointment_date)
