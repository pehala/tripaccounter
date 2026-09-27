// The one rule for which days fold into "Before the trip", shared by the item feed
// and the statistics page so the group holds the same days on both.
export function isBeforeTrip(day, startDate) {
  return Boolean(startDate) && day < startDate;
}
