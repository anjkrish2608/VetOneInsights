-- FINDINGS.md, finding 1: clinics above twice the network rate (recent window).
with ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
)

select
    clinic_name,
    round(100 * no_show_rate_recent, 1) as recent_pct,
    round(100 * network_rate_recent, 1) as network_pct
from ranking
where no_show_rate_recent > 2 * network_rate_recent
order by no_show_rate_recent desc
