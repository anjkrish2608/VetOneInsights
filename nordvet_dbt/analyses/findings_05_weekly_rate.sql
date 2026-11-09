-- FINDINGS.md, finding 3: weekly network no-show rate over settled days, active clinics.
with daily as (
    select * from {{ ref('mart_clinic_daily_noshows') }}
)

select
    date_trunc('week', appointment_date)                             as week_starting,
    round(100.0 * sum(no_shows) / sum(completed + no_shows), 1)      as rate_pct
from daily
where is_settled
  and is_active
group by week_starting
order by week_starting
