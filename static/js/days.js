// The one rule for which days fold into "Before the trip", named once so every
// page that groups by day holds the same days in it.
export function isBeforeTrip(day, startDate) {
  return Boolean(startDate) && day < startDate;
}
