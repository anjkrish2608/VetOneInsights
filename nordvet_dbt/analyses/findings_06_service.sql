-- FINDINGS.md, finding 4: no-show rate by service, settled days, active clinics.
with appointments as (
    select * from {{ ref('stg_vetone__appointments') }}
),

clinics as (
    select * from {{ ref('stg_vetone__clinics') }}
),

ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
),

settled_until as (
    select max(settled_until) as settled_until
    from ranking
),

settled_active as (
    select appointments.*
    from appointments
    inner join clinics
        on appointments.clinic_id = clinics.clinic_id
        and clinics.is_active
    cross join settled_until
    where appointments.scheduled_date_local <= settled_until.settled_until
)

select
    service,
    round(100.0 * sum(case when status = 'no_show' then 1 else 0 end)
          / sum(case when status in ('completed', 'no_show') then 1 else 0 end), 1) as rate_pct,
    sum(case when status in ('completed', 'no_show') then 1 else 0 end)             as attended_or_missed
from settled_active
group by service
order by rate_pct desc
