-- One row per appointment: its latest version, with deleted appointments removed.
-- Order matters: dedupe first, then drop deleted (D-dedupe, D-deleted).
with source as (
    select * from {{ source('vetone', 'raw_appointments') }}
),

typed as (
    select
        id                                    as appointment_id,
        clinic_id,
        service,
        status,
        duration_minutes,
        -- API sends local time with offset, e.g. 2026-11-05T08:00+01:00 (D-timestamps)
        cast(scheduled_at as timestamptz)     as scheduled_at,
        cast(left(scheduled_at, 16) as timestamp) as scheduled_at_local,
        cast(left(scheduled_at, 10) as date)  as scheduled_date_local,
        cast(created_at as timestamptz)       as created_at,
        cast(updated_at as timestamptz)       as updated_at,
        cast(cancelled_at as timestamptz)     as cancelled_at,
        cast(deleted_at as timestamptz)       as deleted_at,
        _loaded_at
    from source
),

latest_version as (
    select *
    from typed
    qualify row_number() over (
        partition by appointment_id
        order by updated_at desc, _loaded_at desc
    ) = 1
)

select
    appointment_id,
    clinic_id,
    service,
    status,
    duration_minutes,
    scheduled_at,
    scheduled_at_local,
    scheduled_date_local,
    created_at,
    updated_at,
    cancelled_at,
    _loaded_at
from latest_version
where deleted_at is null
