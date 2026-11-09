-- One row per active clinic: no-show rate over settled days, in two windows
-- (D-ranking-window). Ranked on the recent window; the history window is the baseline.
with settled_days as (
    select *
    from {{ ref('mart_clinic_daily_noshows') }}
    where is_settled
      and is_active                       -- inactive clinics are not ranked (D-inactive)
),

per_clinic as (
    select
        clinic_id,
        clinic_name,
        country,
        -- recent window: the newest settled days, e.g. days_ago 4..31 for 3 + 28
        sum(case when days_ago <= {{ var('unsettled_days') }} + {{ var('ranking_window_days') }}
            then completed else 0 end)                              as completed_recent,
        sum(case when days_ago <= {{ var('unsettled_days') }} + {{ var('ranking_window_days') }}
            then no_shows else 0 end)                               as no_shows_recent,
        sum(case when days_ago <= {{ var('unsettled_days') }} + {{ var('ranking_window_days') }}
            then lost_vet_minutes else 0 end)                       as lost_vet_minutes_recent,
        -- history window: every settled day loaded (from BACKFILL_FROM)
        sum(completed)                                              as completed_history,
        sum(no_shows)                                               as no_shows_history,
        sum(lost_vet_minutes)                                       as lost_vet_minutes_history,
        min(appointment_date)                                       as history_from,
        max(appointment_date)                                       as settled_until
    from settled_days
    group by clinic_id, clinic_name, country
),

with_rates as (
    select
        *,
        cast(no_shows_recent as double)
            / nullif(completed_recent + no_shows_recent, 0)         as no_show_rate_recent,
        cast(no_shows_history as double)
            / nullif(completed_history + no_shows_history, 0)       as no_show_rate_history
    from per_clinic
),

network as (
    select
        cast(sum(no_shows_recent) as double)
            / nullif(sum(completed_recent + no_shows_recent), 0)    as network_rate_recent,
        cast(sum(no_shows_history) as double)
            / nullif(sum(completed_history + no_shows_history), 0)  as network_rate_history
    from per_clinic
)

select
    rank() over (order by with_rates.no_show_rate_recent desc nulls last) as rank_recent,
    with_rates.clinic_id,
    with_rates.clinic_name,
    with_rates.country,
    with_rates.no_show_rate_recent,
    with_rates.no_shows_recent,
    with_rates.completed_recent,
    with_rates.lost_vet_minutes_recent,
    round(with_rates.lost_vet_minutes_recent / 60.0, 1)            as lost_vet_hours_recent,
    network.network_rate_recent,
    round((with_rates.no_show_rate_recent - network.network_rate_recent) * 100, 2)
                                                                   as vs_network_pp_recent,
    with_rates.no_show_rate_history,
    with_rates.no_shows_history,
    with_rates.completed_history,
    with_rates.lost_vet_minutes_history,
    round(with_rates.lost_vet_minutes_history / 60.0, 1)           as lost_vet_hours_history,
    network.network_rate_history,
    round((with_rates.no_show_rate_history - network.network_rate_history) * 100, 2)
                                                                   as vs_network_pp_history,
    with_rates.history_from,
    with_rates.settled_until
from with_rates
cross join network
