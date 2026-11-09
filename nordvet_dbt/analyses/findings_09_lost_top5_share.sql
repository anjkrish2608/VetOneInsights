-- FINDINGS.md, finding 6: share of lost vet time from the 5 clinics that lose the most.
with ranking as (
    select * from {{ ref('mart_clinic_noshow_ranking') }}
),

ranked_by_loss as (
    select
        lost_vet_minutes_recent,
        rank() over (order by lost_vet_minutes_recent desc) as loss_rank
    from ranking
)

select
    round(100.0 * sum(case when loss_rank <= 5 then lost_vet_minutes_recent else 0 end)
          / sum(lost_vet_minutes_recent)) as top5_share_pct
from ranked_by_loss
