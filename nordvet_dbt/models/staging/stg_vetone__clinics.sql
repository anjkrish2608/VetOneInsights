-- One row per clinic, from the most recent snapshot (D-clinics).
with latest_run as (
    select max(_run_id) as _run_id
    from {{ source('vetone', 'raw_clinics') }}
),

latest_clinics as (
    select clinics.*
    from {{ source('vetone', 'raw_clinics') }} as clinics
    inner join latest_run
        on clinics._run_id = latest_run._run_id
)

select
    id                       as clinic_id,
    name                     as clinic_name,
    city,
    country,
    timezone,
    active                   as is_active,
    cast(opened_on as date)  as opened_on,
    _loaded_at
from latest_clinics
