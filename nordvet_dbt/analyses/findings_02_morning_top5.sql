-- FINDINGS.md, morning view: the 5 clinics with the most no-shows on the last open day
-- (D-morning-sample).
with daily as (
    select * from {{ ref('mart_clinic_daily_noshows') }}
),

ranked as (
    select
        clinic_name,
        appointments,
        no_shows,
        awaiting_status,
        round(100 * no_show_rate, 1) as rate_pct,
        lost_vet_minutes,
        row_number() over (
            order by no_shows desc, awaiting_status desc, appointments desc
        ) as position
    from daily
    where is_last_open_day
)

select
    position,
    clinic_name,
    appointments,
    no_shows,
    awaiting_status,
    rate_pct,
    lost_vet_minutes
from ranked
where position <= 5
order by position
