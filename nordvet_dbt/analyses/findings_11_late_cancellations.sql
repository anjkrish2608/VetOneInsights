-- FINDINGS.md, question 1: cancellations recorded after the appointment started
-- (D-late-cancellations).
with appointments as (
    select * from {{ ref('stg_vetone__appointments') }}
),

ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
),

settled_until as (
    select max(settled_until) as settled_until
    from ranking
),

settled_cancellations as (
    select appointments.*
    from appointments
    cross join settled_until
    where appointments.status = 'cancelled'
      and appointments.scheduled_date_local <= settled_until.settled_until
)

select
    count(*)                                                        as cancelled,
    sum(case when cancelled_at > scheduled_at then 1 else 0 end)    as after_start,
    round(100.0 * sum(case when cancelled_at > scheduled_at then 1 else 0 end) / count(*)) as pct
from settled_cancellations
