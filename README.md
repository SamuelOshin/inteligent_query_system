# Profile Intelligence Service — Stage 2

## Setup

```bash
uv sync
cp .env.example .env   # set DATABASE_URL
uv run fastapi dev app/main.py
```

## Seed the Database

```bash
python scripts/seed.py --file path/to/profiles.json
```

---

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles` | List profiles with filters, sort, pagination |
| GET | `/api/profiles/search?q=` | Natural language search |
| GET | `/api/profiles/{id}` | Get single profile by UUID |
| DELETE | `/api/profiles/{id}` | Delete a profile |

### Filter Parameters (`GET /api/profiles`)

| Param | Type | Example |
|-------|------|---------|
| `gender` | string | `male` / `female` |
| `age_group` | string | `child` / `teenager` / `adult` / `senior` |
| `country_id` | string | `NG` / `KE` |
| `min_age` | int | `25` |
| `max_age` | int | `50` |
| `min_gender_probability` | float | `0.8` |
| `min_country_probability` | float | `0.7` |
| `sort_by` | string | `age` / `created_at` / `gender_probability` |
| `order` | string | `asc` / `desc` |
| `page` | int | `1` |
| `limit` | int | `10` (max 50) |

---

## Natural Language Query — Approach

### How It Works

The NL parser (`app/utils/query_parser.py`) uses **rule-based keyword scanning** — no AI or LLMs involved.

**Steps:**
1. Lowercase + tokenize the input string
2. Scan tokens against a gender keyword map
3. Scan tokens against an age_group keyword map
4. Use regex to detect `"above/over/older than <number>"` for `min_age`
5. Use regex to detect `"from/in <country name>"` and map to ISO country code
6. If zero filters extracted → return error

The extracted filter dict is then passed directly into the same filter builder used by `GET /api/profiles`, so there is no duplicated query logic.

### Supported Keywords

**Gender:**
- `male`, `males`, `men`, `man` → `gender=male`
- `female`, `females`, `women`, `woman` → `gender=female`

**Age Group:**
- `young`, `youth` → `min_age=16`, `max_age=24` (parsing-only, not stored age group)
- `child`, `children` → `age_group=child`
- `teen`, `teens`, `teenager`, `teenagers` → `age_group=teenager`
- `adult`, `adults` → `age_group=adult`
- `senior`, `seniors`, `elderly`, `old` → `age_group=senior`

**Country (after "from" or "in"):**
- `"from nigeria"` → `country_id=NG`
- `"in kenya"` → `country_id=KE`
- `"from angola"` → `country_id=AO`

**Min Age:**
- `"above 30"` → `min_age=30`
- `"over 25"` → `min_age=25`
- `"older than 40"` → `min_age=40`

---

### Working Examples

**Example 1:**
```
GET /api/profiles/search?q=young males from nigeria
→ gender=male, min_age=16, max_age=24, country_id=NG
```

**Example 2:**
```
GET /api/profiles/search?q=females above 30
→ gender=female, min_age=30
```

**Example 3:**
```
GET /api/profiles/search?q=people from angola
→ country_id=AO
```

**Example 4:**
```
GET /api/profiles/search?q=male and female teenagers above 17
→ age_group=teenager, min_age=17
```

---

### Limitations

The following are **not supported** by the current parser:

- **Negation:** `"not male"`, `"excluding nigeria"` — ignored entirely
- **Age ranges:** `"between 20 and 30"` — only `above/over/older than` is handled
- **Typo tolerance:** `"nigerria"`, `"femal"` — exact keyword match only
- **Multiple countries:** `"from nigeria or kenya"` — only first match used
- **Sorting/pagination in NL:** `"top 5 young males"` — not interpreted
- **Partial country names:** `"people from the UK"` → `"uk"` works, `"united kingd"` does not
- **Complex boolean:** `"males and females"` — gender filter is omitted

---

## Age Classification

| Age Range | Group |
|-----------|-------|
| 0 – 12 | `child` |
| 13 – 19 | `teenager` |
| 20 – 59 | `adult` |
| 60+ | `senior` |

---

## Project Structure

```
app/
├── main.py
├── core/config.py
├── db/database.py
├── models/profile.py
├── schemas/profile.py
├── routes/profiles.py
├── services/profile_service.py
└── utils/
    ├── pagination.py
    └── query_parser.py
scripts/
└── seed.py
requirements.txt
```
