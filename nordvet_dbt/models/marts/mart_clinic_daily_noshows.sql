-- One row per clinic per local day, for every day before the as-of date (D-marts).
-- Mette's "yesterday" = the rows where is_last_open_day is true (D-last-open-day).
with as_of as (
    select
        {% if var('as_of_date', none) %}
        cast('{{ var("as_of_date") }}' as date)
        {% else %}
        cast(timezone('Europe/Copenhagen', current_timestamp) as date)
        {% endif %} as as_of_date
),

-- clinics are re-fetched on every successful run, so their load time is the last load
last_load as (
    select max(_loaded_at) as last_loaded_at
    from {{ ref('stg_vetone__clinics') }}
),

past_appointments as (
    select appointments.*
    from {{ ref('stg_vetone__appointments') }} as appointments
    cross join as_of
    where appointments.scheduled_date_local < as_of.as_of_date
),

daily_counts as (
    select
        clinic_id,
        scheduled_date_local                                            as appointment_date,
        count(*)                                                        as appointments,
        sum(case when status = 'completed' then 1 else 0 end)          as completed,
        sum(case when status = 'no_show' then 1 else 0 end)            as no_shows,
        sum(case when status = 'cancelled' then 1 else 0 end)          as cancelled,
        sum(case when status = 'booked' then 1 else 0 end)             as awaiting_status,
        sum(case when status = 'no_show' then duration_minutes else 0 end) as lost_vet_minutes
    from past_appointments
    group by clinic_id, scheduled_date_local
),

with_clinic as (
    select
        daily_counts.*,
        clinics.clinic_name,
        clinics.country,
        clinics.is_active,
        as_of.as_of_date,
        last_load.last_loaded_at,
        datediff('day', daily_counts.appointment_date, as_of.as_of_date) as days_ago
    from daily_counts
    cross join as_of
    cross join last_load
    left join {{ ref('stg_vetone__clinics') }} as clinics
        on daily_counts.clinic_id = clinics.clinic_id
)

select
    clinic_id || '_' || strftime(appointment_date, '%Y-%m-%d')     as clinic_day_id,
    clinic_id,
    clinic_name,
    country,
    is_active,
    appointment_date,
    as_of_date,
    last_loaded_at,
    days_ago,
    days_ago > {{ var('unsettled_days') }}                          as is_settled,
    -- most recent day before as_of with any appointments in the network:
    -- on a Monday this is Saturday, since clinics are closed on Sundays
    appointment_date = max(appointment_date) over ()               as is_last_open_day,
    appointments,
    completed,
    no_shows,
    cancelled,
    awaiting_status,
    -- confirmed rate: cancelled excluded, awaiting not counted (D-formula)
    cast(no_shows as double) / nullif(completed + no_shows, 0)     as no_show_rate,
    -- lower bound: every awaiting appointment turns out completed (D-metric)
    cast(no_shows as double)
        / nullif(completed + no_shows + awaiting_status, 0)         as no_show_rate_lower,
    -- upper bound: every awaiting appointment turns out a no-show (D-metric)
    cast(no_shows + awaiting_status as double)
        / nullif(completed + no_shows + awaiting_status, 0)         as no_show_rate_upper,
    lost_vet_minutes
from with_clinic
