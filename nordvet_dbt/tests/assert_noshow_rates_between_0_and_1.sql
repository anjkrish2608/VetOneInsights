-- Every no-show rate must be a share between 0 and 1. Returns offending rows (D-singular-tests).
with daily_rates as (
    select clinic_day_id as row_key, 'no_show_rate' as rate_name, no_show_rate as rate
    from {{ ref('mart_clinic_daily_noshows') }}
    union all
    select clinic_day_id, 'no_show_rate_lower', no_show_rate_lower
    from {{ ref('mart_clinic_daily_noshows') }}
    union all
    select clinic_day_id, 'no_show_rate_upper', no_show_rate_upper
    from {{ ref('mart_clinic_daily_noshows') }}
),

ranking_rates as (
    select clinic_id as row_key, 'no_show_rate_recent' as rate_name, no_show_rate_recent as rate
    from {{ ref('mart_clinic_noshow_ranking') }}
    union all
    select clinic_id, 'no_show_rate_history', no_show_rate_history
    from {{ ref('mart_clinic_noshow_ranking') }}
),

all_rates as (
    select * from daily_rates
    union all
    select * from ranking_rates
)

select *
from all_rates
where rate < 0 or rate > 1
