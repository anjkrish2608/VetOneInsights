-- FINDINGS.md, finding 6: vet hours lost to no-shows in the recent window.
-- 525 h / 4 weeks = 131 h a week, and 131 h / 37 h full-time week = about 3.5 full-time vets (D-fte).
with ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
)

select
    round(sum(lost_vet_minutes_recent) / 60.0)            as lost_hours_recent,
    round(sum(lost_vet_minutes_recent) / 60.0 / 4 / 37, 1) as full_time_vets_37h
from ranking
