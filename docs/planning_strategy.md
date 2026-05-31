# Planning Strategy

## 1. Purpose

This document defines the planning strategy for LocalLife Agent.

The system should transform a vague local-life request into a feasible, executable 4-6 hour plan.

The goal is not to recommend many places. The goal is to arrange one complete plan that the user can confirm and execute.

## 2. Core Planning Philosophy

The planning pipeline follows this principle:

```txt
Understand constraints first, then search, then verify, then compose, then repair.
```

The Agent must not invent availability, tickets, seats, booking results, or queue status.

These facts must come from MockAPI tools.

## 3. Planning Pipeline

```txt
User Message
  ↓
Intent Parser
  ↓
Structured Intent
  ↓
Constraint Builder
  ↓
Candidate Search
  ↓
Hard Constraint Filtering
  ↓
Soft Ranking
  ↓
Time Allocation
  ↓
Availability Check
  ↓
Plan Composition
  ↓
Exception Repair
  ↓
Final Executable Plan
```

## 4. Intent Parsing

The Intent Parser converts a natural language message into structured intent.

### 4.1 Input

Example:

```txt
今天下午空的，想和老婆孩子出去玩几个小时，别离家太远，孩子5岁，老婆最近在减肥。
```

### 4.2 Output

```json
{
  "scenario_type": "family",
  "group_size": 3,
  "group_profile": {
    "adults": 2,
    "children": 1,
    "child_age": 5
  },
  "time_window": {
    "date": "today",
    "start_time": "14:00",
    "duration_hours": 5
  },
  "location_constraint": {
    "anchor": "home",
    "max_distance_km": 6
  },
  "preferences": ["child_friendly", "healthy_food", "low_burden"],
  "restrictions": ["avoid_long_queue", "avoid_too_far"]
}
```

## 5. Scenario Types

### 5.1 Family Scenario

Typical constraints:

* Child-friendly
* Safe
* Indoor preferred if weather is uncertain
* Low travel burden
* Healthy or low-calorie food if requested
* Earlier dinner time
* More buffer time

Recommended structure:

```txt
Departure
→ Child-friendly activity
→ Short buffer / transfer
→ Healthy dinner
→ Optional light walk or dessert
→ Return
```

### 5.2 Friend Scenario

Typical constraints:

* Social
* Photo-friendly
* Group-friendly restaurant
* Flexible activity
* Slightly later dinner acceptable
* More novelty acceptable

Recommended structure:

```txt
Departure
→ Exhibition / citywalk / entertainment
→ Cafe or snack stop
→ Dinner
→ Optional after-dinner activity
→ Return
```

## 6. Time Allocation

The plan should fit within 4-6 hours.

Default family allocation:

```txt
Travel out: 20-40 min
Main activity: 90-120 min
Transfer / buffer: 15-30 min
Dinner: 60-90 min
Optional activity: 0-45 min
Return buffer: 20-40 min
```

Default friend allocation:

```txt
Travel out: 20-40 min
Main activity: 90-120 min
Cafe / citywalk: 30-60 min
Dinner: 90-120 min
Optional activity: 0-60 min
Return buffer: 20-40 min
```

## 7. Constraint Types

## 7.1 Hard Constraints

Hard constraints must be satisfied.

Examples:

* Time window
* Group size
* Ticket availability
* Restaurant seat availability
* Distance limit
* Venue minimum age
* Opening hours
* Booking feasibility

If a hard constraint fails, the candidate must be rejected or repaired.

## 7.2 Soft Constraints

Soft constraints affect ranking.

Examples:

* Healthy food
* Child friendliness
* Photo friendliness
* Price
* Novelty
* Lower queue risk
* Shorter travel distance
* Better group atmosphere

Soft constraints should produce reasons in the final plan.

## 8. Candidate Search Strategy

The planner should search candidates by scenario.

### 8.1 Family Venue Search

Search tags:

* `child_friendly`
* `indoor`
* `family`
* `low_burden`
* `near_home`

### 8.2 Friend Venue Search

Search tags:

* `social`
* `photo_friendly`
* `citywalk`
* `exhibition`
* `group_activity`

### 8.3 Family Restaurant Search

Search tags:

* `healthy`
* `low_calorie`
* `child_friendly`
* `low_queue`

### 8.4 Friend Restaurant Search

Search tags:

* `group_friendly`
* `social`
* `dinner`
* `popular`
* `near_activity`

## 9. Ranking Strategy

Candidates should be scored with a simple explainable formula.

Example:

```txt
score =
  scenario_match_score * 0.30
+ distance_score * 0.20
+ availability_score * 0.20
+ preference_score * 0.20
+ price_score * 0.10
```

For MVP, this can be implemented as deterministic Python rules.

Do not rely only on LLM ranking.

## 10. Availability Check

Before a plan is returned to the user, the system must check:

* Activity ticket availability
* Restaurant seat availability
* Booking time slot
* Group size compatibility

A plan that has not passed availability checks should not be marked executable.

## 11. Plan Composition

The final plan should include:

* Plan title
* Summary
* Timeline
* Locations
* Start and end time
* Estimated cost
* Availability status
* Booking requirements
* Reasons
* Risk notes
* Execution actions

Example item:

```json
{
  "item_type": "meal",
  "start_time": "17:30",
  "end_time": "18:45",
  "name": "轻食研究所",
  "reason": "低卡健康，适合正在减肥的家庭成员，且有儿童餐椅",
  "availability_status": "available",
  "booking_required": true
}
```

## 12. Exception Handling

The planner should repair failures automatically when possible.

### 12.1 Restaurant No Seats

Repair order:

1. Try adjacent time slots.
2. Try similar restaurants nearby.
3. Try changing meal order while preserving main activity.
4. If still failing, return a risk note and ask for confirmation.

### 12.2 Venue No Tickets

Repair order:

1. Try another time slot.
2. Try same category venue nearby.
3. Try another suitable activity category.
4. Recalculate the timeline.

### 12.3 Time Conflict

Repair order:

1. Remove optional activity.
2. Shorten flexible activity.
3. Replace far destination.
4. Move dinner time if available.
5. Return shortened plan if necessary.

### 12.4 Tool Timeout

Repair order:

1. Retry once.
2. Use cached mock data.
3. Mark uncertainty in trace.
4. Continue only if the plan remains safe and reasonable.

## 13. Tool Calling Chain

Family happy path:

```txt
parse_intent
→ search_venues
→ check_venue_availability
→ search_restaurants
→ check_restaurant_availability
→ compose_plan
→ user_confirm
→ book_venue
→ reserve_restaurant
→ create_share_message
```

Friend happy path:

```txt
parse_intent
→ search_venues
→ check_venue_availability
→ search_restaurants
→ check_restaurant_availability
→ compose_plan
→ user_confirm
→ book_venue
→ reserve_restaurant
→ create_share_message
```

Failure path:

```txt
tool_failure
→ classify_failure
→ select_repair_strategy
→ retry_tool_or_replace_candidate
→ revalidate_plan
→ return_repaired_plan
```

## 14. Planning Quality Checklist

Before returning a plan, check:

* Does it fit 4-6 hours?
* Does every activity have a time range?
* Is there enough travel and buffer time?
* Does the restaurant have seats?
* Does the venue have tickets?
* Does the plan match the group?
* Does the plan explain why it fits?
* Are execution actions ready?
* Are fallback notes visible if repair happened?

## 15. MVP Implementation Recommendation

For MVP:

* Use LLM for intent parsing.
* Use deterministic rules for planning and constraints.
* Use MockAPI for facts.
* Use rule-based fallback.
* Store tool traces.

Do not use fully autonomous multi-agent planning in MVP.
