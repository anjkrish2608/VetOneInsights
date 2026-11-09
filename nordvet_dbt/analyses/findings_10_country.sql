-- FINDINGS.md, finding 7: no-show rate by country (recent window).
with ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
)

select
    country,
    round(100.0 * sum(no_shows_recent) / sum(completed_recent + no_shows_recent), 1) as recent_pct,
    count(*)                                                                          as clinics
from ranking
group by country
order by country
