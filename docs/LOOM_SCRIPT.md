# Loom walkthrough script

Target length: 7 to 8 minutes (Spotter asks for 5 to 10). Record at 1440 x 900 with the hosted
application open in one tab and the repository in another. Times are a guide.

Before recording: open the app, check that the demo trip works, and have `spec.md`,
`backend/risk/classification.py` and `backend/tests/test_risk_classification.py` open in the
editor.

## 0:00 Introduction (30 s)

- "This is StormRoute, my submission for the Spotter full stack assessment. It helps a truck
  driver choose the safer route by checking the forecast at each point of the route, at the time
  the truck is expected to be there."
- Stack in one sentence: React and TypeScript on the front, Django REST Framework on the back,
  real routes from Valhalla and real forecasts from Open-Meteo, with no API keys.

## 0:30 The demo trip (1 min 30 s)

- Say why there is a demo: "Real weather is usually calm, so the app has a clearly labeled demo
  with a recorded real route and simulated weather. The yellow band stays on screen the whole
  time so it cannot be mistaken for a real forecast."
- Press **Run the demo trip**. Point out the three routes on the map and the three cards.
- Read the recommendation: Route C, because Routes A and B have No Travel conditions.
- Point at the risk ribbon on Route A: "Each stretch is as wide as the miles that checkpoint
  stands for, colored by the risk when the truck arrives there."

## 2:00 Checkpoint details and the load rule (1 min 15 s)

- Click the dark segment on Route A (mile 375). Show the panel: arrival in local time, the
  forecast hour used, wind 50.1 mph.
- "Wind between 45 and 55 mph is Severe, but with a load over 30,000 pounds it becomes No Travel.
  That is Spotter's second load rule, and the panel says so."
- Change the load weight to **28000** and press **Compare routes**. Routes A and B are no longer
  blocked. The recommendation is still Route C, now because it avoids 50 miles of severe weather,
  and it says how much longer it takes.
- Mention the strict comparison: 30,000 exactly does not trigger the rule, 30,001 does. It is
  tested at that boundary.

## 3:15 Departure time and the interval (45 s)

- Move the departure 12 hours later and compare. The storm is gone when the truck gets there, so
  the fastest route wins. "Changing the departure moves every arrival time onto a different
  forecast hour."
- Switch the interval to 10 miles and compare: more checkpoints, the same logic.

## 4:00 Corridor heatmap and slider (1 min)

- Drag the forecast slider. "This is the forecast around the routes for the next 48 hours, for
  this load. The dark marker is where the truck would be at that time."
- "Moving the slider makes no network request. Every cell already carries its risk for all 49
  hours, and the map only changes what it paints." Mention that an end-to-end test asserts this.
- Say the difference out loud: the shading is the forecast at the chosen time; the checkpoints
  keep showing the risk at their own arrival time.

## 5:00 A live trip (45 s)

- Type a real origin and destination (for example Chicago and Nashville), pick them from the
  suggestions and compare. The yellow band disappears: this is live data.
- Point out the "Analyzed trip" line, the three real routes and the footer with the data sources
  and the routing limitation.

## 5:45 How it is built (1 min 15 s)

- Show `backend/risk/classification.py`: one pure module for the rules, used for checkpoints and
  for heatmap cells.
- Show the boundary table in `backend/tests/test_risk_classification.py`: 24.99 and 25 mph,
  30,000 and 30,001 lb, 1.00 and 1.001 inches.
- Mention the numbers: 384 backend tests, 136 frontend tests, 22 end-to-end runs at desktop and
  phone widths.
- Show `spec.md` briefly: the specification, the decision log and the review record. "I built it
  as five reviewed pull requests. Each one was reviewed before I merged it."

## 7:00 Limitations and close (45 s)

- "These are standard driving routes. Truck restrictions like bridge weights and low clearances
  are not applied, and the app says so on every result."
- "Arrival times assume continuous driving. Rest breaks and live traffic are not modelled."
- "A route with missing weather is marked unverified and is never recommended. Missing data is
  never treated as safe."
- AI assistance: say it plainly, as in the README.
- Thank the reviewer and stop.

## If something fails during recording

- If the routing or weather service is slow or down, the app shows a clear error with a
  **Try again** button. Show it, then continue with the demo trip.
