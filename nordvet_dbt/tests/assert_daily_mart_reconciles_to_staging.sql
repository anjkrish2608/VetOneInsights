-- No appointments are lost or double-counted between staging and the daily mart:
-- the mart's total for each day must equal the staging count for that day.
-- Returns days where they differ.
with mart_totals as (
    select appointment_date, sum(appointments) as mart_appointments
    from {{ ref('mart_clinic_daily_noshows') }}
    group by appointment_date
),

as_of as (
    select max(as_of_date) as as_of_date
    from {{ ref('mart_clinic_daily_noshows') }}
),

staging_totals as (
    select scheduled_date_local as appointment_date, count(*) as staging_appointments
    from {{ ref('stg_vetone__appointments') }}
    cross join as_of
    where scheduled_date_local < as_of.as_of_date
    group by scheduled_date_local
)

select
    coalesce(staging_totals.appointment_date, mart_totals.appointment_date) as appointment_date,
    staging_totals.staging_appointments,
    mart_totals.mart_appointments
from staging_totals
full outer join mart_totals
    on staging_totals.appointment_date = mart_totals.appointment_date
where staging_totals.staging_appointments is distinct from mart_totals.mart_appointments
