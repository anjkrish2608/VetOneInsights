-- FINDINGS.md, findings 1 and 2: the 3 worst and 3 best clinics over the recent window.
with ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
),

clinic_count as (
    select count(*) as clinics
    from ranking
)

select
    ranking.rank_recent,
    ranking.clinic_name,
    round(100 * ranking.no_show_rate_recent, 1)  as recent_pct,
    ranking.no_shows_recent,
    ranking.lost_vet_hours_recent,
    round(100 * ranking.no_show_rate_history, 1) as history_pct
from ranking
cross join clinic_count
where ranking.rank_recent <= 3
   or ranking.rank_recent > clinic_count.clinics - 3
order by ranking.rank_recent
