# MockAPI Design

## 1. Purpose

MockAPI simulates local-life platform capabilities for the LocalLife Agent demo.

It provides deterministic APIs for:

- Venue search
- Venue availability
- Venue booking
- Restaurant search
- Restaurant availability
- Restaurant reservation
- Optional order creation
- Share message generation

The MockAPI is not a real Meituan API integration.

It exists to make the Agent demo executable, observable, and reproducible.

## 2. Design Principles

1. MockAPI must be deterministic.
2. MockAPI should support both happy paths and failure paths.
3. MockAPI responses should look realistic enough for demo.
4. Tool latency should be controllable.
5. MockAPI should not contain planning logic.
6. MockAPI should return facts, not final plans.
7. Failure scenarios should be triggered by explicit data.

## 3. Base URL

For local development:

```txt
http://localhost:8001/mock
````

If MockAPI is mounted inside the same FastAPI app:

```txt
/mock
```

## 4. Data Files

Mock data lives in:

```txt
src/mock_api/data/
├── venues.json
├── restaurants.json
├── availability.json
└── orders.json
```

## 5. Venue Data Model

Example:

```json
{
  "id": "venue_family_001",
  "name": "云朵亲子乐园",
  "category": "indoor_playground",
  "location": "望京",
  "address": "望京中心商场 3 层",
  "distance_km": 3.2,
  "duration_minutes": 90,
  "tags": ["child_friendly", "indoor", "family", "low_burden"],
  "suitable_for": ["family"],
  "min_age": 3,
  "ticket_required": true,
  "price_per_person": 88,
  "opening_hours": {
    "start": "10:00",
    "end": "21:00"
  }
}
```

## 6. Restaurant Data Model

Example:

```json
{
  "id": "rest_family_001",
  "name": "轻食研究所",
  "category": "healthy_food",
  "location": "望京",
  "address": "望京 SOHO B1",
  "distance_km": 3.8,
  "tags": ["healthy", "low_calorie", "child_friendly", "low_queue"],
  "suitable_for": ["family"],
  "avg_price": 85,
  "opening_hours": {
    "start": "11:00",
    "end": "21:30"
  },
  "features": ["儿童椅", "低卡套餐", "少油少盐"]
}
```

## 7. Availability Data Model

Example:

```json
{
  "venue_availability": {
    "venue_family_001": {
      "14:30": {
        "available_tickets": 12,
        "status": "available"
      },
      "15:00": {
        "available_tickets": 0,
        "status": "sold_out"
      }
    }
  },
  "restaurant_availability": {
    "rest_family_001": {
      "17:00": {
        "available_seats": 4,
        "queue_minutes": 0,
        "status": "available"
      },
      "17:30": {
        "available_seats": 0,
        "queue_minutes": 60,
        "status": "full"
      }
    }
  }
}
```

## 8. API Endpoints

## 8.1 Search Venues

```txt
GET /mock/venues/search
```

Query parameters:

```txt
scenario_type: family | friends
tags: comma-separated string
max_distance_km: number
group_size: number
```

Example:

```txt
GET /mock/venues/search?scenario_type=family&tags=child_friendly,indoor&max_distance_km=6&group_size=3
```

Response:

```json
{
  "items": [
    {
      "id": "venue_family_001",
      "name": "云朵亲子乐园",
      "category": "indoor_playground",
      "location": "望京",
      "distance_km": 3.2,
      "duration_minutes": 90,
      "tags": ["child_friendly", "indoor", "family"],
      "price_per_person": 88,
      "reason_tags": ["适合5岁儿童", "室内", "距离近"]
    }
  ]
}
```

## 8.2 Check Venue Availability

```txt
GET /mock/venues/{venue_id}/availability
```

Query parameters:

```txt
date: string
time: string
group_size: number
```

Response:

```json
{
  "venue_id": "venue_family_001",
  "time": "14:30",
  "available": true,
  "available_tickets": 12,
  "status": "available"
}
```

## 8.3 Book Venue

```txt
POST /mock/venues/{venue_id}/book
```

Request:

```json
{
  "date": "2026-05-30",
  "time": "14:30",
  "group_size": 3,
  "user_name": "小明"
}
```

Response:

```json
{
  "booking_id": "book_venue_001",
  "venue_id": "venue_family_001",
  "status": "confirmed",
  "message": "云朵亲子乐园 14:30 门票已预约"
}
```

## 8.4 Search Restaurants

```txt
GET /mock/restaurants/search
```

Query parameters:

```txt
scenario_type: family | friends
tags: comma-separated string
max_distance_km: number
near_location: string
group_size: number
```

Example:

```txt
GET /mock/restaurants/search?scenario_type=family&tags=healthy,low_calorie&near_location=望京&group_size=3
```

Response:

```json
{
  "items": [
    {
      "id": "rest_family_001",
      "name": "轻食研究所",
      "category": "healthy_food",
      "location": "望京",
      "distance_km": 3.8,
      "avg_price": 85,
      "tags": ["healthy", "low_calorie", "child_friendly"],
      "reason_tags": ["低卡", "适合减脂", "儿童友好"]
    }
  ]
}
```

## 8.5 Check Restaurant Availability

```txt
GET /mock/restaurants/{restaurant_id}/availability
```

Query parameters:

```txt
date: string
time: string
group_size: number
```

Response:

```json
{
  "restaurant_id": "rest_family_001",
  "time": "17:30",
  "available": false,
  "available_seats": 0,
  "queue_minutes": 60,
  "status": "full"
}
```

## 8.6 Reserve Restaurant

```txt
POST /mock/restaurants/{restaurant_id}/reserve
```

Request:

```json
{
  "date": "2026-05-30",
  "time": "17:30",
  "group_size": 3,
  "user_name": "小明"
}
```

Response:

```json
{
  "reservation_id": "reserve_001",
  "restaurant_id": "rest_family_002",
  "status": "confirmed",
  "message": "绿碗轻食 17:30 三人位已预约"
}
```

## 8.7 Create Order

```txt
POST /mock/orders/create
```

Request:

```json
{
  "order_type": "cake_or_flower",
  "target_location": "rest_family_002",
  "delivery_time": "17:30",
  "note": "送到餐厅前台"
}
```

Response:

```json
{
  "order_id": "order_001",
  "status": "confirmed",
  "message": "订单已创建，将在 17:30 前送达餐厅"
}
```

## 8.8 Create Share Message

```txt
POST /mock/messages/share
```

Request:

```json
{
  "recipient_type": "wife",
  "plan_summary": "下午2点出发，先去云朵亲子乐园，再去绿碗轻食吃晚餐。",
  "execution_status": "confirmed"
}
```

Response:

```json
{
  "message_id": "msg_001",
  "text": "搞定了，下午2点出发，先去云朵亲子乐园，17:30 去绿碗轻食吃晚餐，位置已经约好了。"
}
```

## 9. Failure Scenario Design

The MockAPI must include deterministic failure cases.

## 9.1 Restaurant No Seats

Example:

```json
{
  "restaurant_id": "rest_family_001",
  "time": "17:30",
  "available_seats": 0,
  "status": "full"
}
```

Expected planner behavior:

* Try adjacent slots.
* Try alternative healthy restaurants.
* Preserve the main activity if possible.

## 9.2 Venue No Tickets

Example:

```json
{
  "venue_id": "venue_family_001",
  "time": "15:00",
  "available_tickets": 0,
  "status": "sold_out"
}
```

Expected planner behavior:

* Try another venue time.
* Try same category venue nearby.
* Recalculate timeline.

## 9.3 Time Conflict

Example:

```json
{
  "venue_id": "venue_friend_003",
  "duration_minutes": 180,
  "distance_km": 9.5
}
```

Expected planner behavior:

* Reject or shorten the plan.
* Remove optional activity.
* Replace far venue.

## 10. Tool Trace Requirements

Every MockAPI call should produce a trace item:

```json
{
  "tool_name": "check_restaurant_availability",
  "input": {
    "restaurant_id": "rest_family_001",
    "time": "17:30",
    "group_size": 3
  },
  "output": {
    "available": false,
    "status": "full"
  },
  "latency_ms": 120,
  "status": "success"
}
```

## 11. Latency Simulation

For demo, default MockAPI latency should be low:

```txt
100ms - 500ms
```

Optional failure testing can simulate:

```txt
3000ms timeout
```

## 12. MVP Data Requirements

Minimum data:

* 4 family venues
* 4 friend venues
* 4 family restaurants
* 4 friend restaurants
* At least 1 no-seat restaurant case
* At least 1 sold-out venue case
* At least 1 time-conflict case

## 13. Non-goals

MockAPI should not:

* Connect to real Meituan services
* Process real payment
* Use real user data
* Make real reservations
* Contain final planning logic
