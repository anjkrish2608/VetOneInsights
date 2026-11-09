-- lower bound <= confirmed rate <= upper bound on every clinic-day.
-- A small tolerance absorbs floating-point rounding. Returns offending rows.
select
    clinic_day_id,
    no_show_rate_lower,
    no_show_rate,
    no_show_rate_upper
from {{ ref('mart_clinic_daily_noshows') }}
where no_show_rate is not null
  and (
      no_show_rate_lower > no_show_rate + 1e-9
      or no_show_rate > no_show_rate_upper + 1e-9
  )
