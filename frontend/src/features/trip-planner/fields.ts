/** Request fields that have an input in the trip form, where their error message is shown. */
export const TRIP_FORM_FIELDS = [
  'origin',
  'destination',
  'departure_time',
  'load_weight_lb',
] as const

export type TripFormField = (typeof TRIP_FORM_FIELDS)[number]
