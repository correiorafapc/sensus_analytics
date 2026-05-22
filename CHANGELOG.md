# Changelog

All notable changes to the Sensus Analytics Integration are documented here.

---

## [2.0.0] - 2026-05-21

### Removed
- **Water Today Usage** and **Electric Today Usage** sensors removed — redundant since `Water Daily Usage` / `Electric Daily Usage` already provide today's accurate total directly from the widget API, matching the portal exactly
- Midnight odometer persistence logic removed from coordinator (no longer needed)


### Fixed
- **Water/Electric Daily Usage sensor incorrectly named** — was called "Yesterday Total Usage" but the widget API actually returns today's running total, not yesterday's. Renamed to "Water Daily Usage" / "Electric Daily Usage"
- **Today Usage double-counting** — API returns 48 hours of data (2 days). Usage sum now filters entries to today's date only, matching the portal value

### Fixed
- **Today Usage inaccurate** — was using odometer delta since midnight which didn't match the web portal. Now fetches today's real hourly data from the API when `showToday=true` and sums the entries for an accurate total
- **Both water and electric** Today Usage sensors benefit from this fix
- Odometer delta is kept as a fallback if today's hourly data is not yet available


### Added
- **Electric Today Usage** sensor — mirrors Water Today Usage, calculates electricity consumption since midnight using odometer delta, persists across HA restarts

### Fixed
- **Midnight odometer** was only being tracked for water meters — now tracked for both water and electric

---

## [1.0.0] - 2026-05-19

### 🚀 Major Release — Water + Electric Merged Integration

This release merges the separate water and electric integrations into a single unified integration. You can now monitor both meters from one place by adding the integration twice — once for Water, once for Electric.

### Added
- **Electric meter support** — full sensor parity with water meter
- **Meter type selector** in config flow — choose `Water` or `Electric` when adding the integration
- **Electric Today Usage** sensor — estimated electricity usage since midnight, persists across HA restarts
- **Water Today Usage** sensor — estimated water usage since midnight, persists across HA restarts
- **Midnight odometer persistence** — today's usage baseline is saved to disk so HA restarts no longer reset the today sensor to zero
- **HACS support** — can now be installed via HACS as a custom repository
- **Custom icon** combining 💧 and 💡
- **`PLATFORMS` constant** in `const.py` — used consistently across `__init__.py` for setup and unload

### Changed
- **Fully async** — replaced blocking `requests` library with `aiohttp`, consistent with HA best practices
- **Poll interval** changed from 5 minutes to 30 minutes — data only updates hourly so frequent polling was wasteful
- **Sensor names** renamed across the board for clarity:

  | Old Name | New Name |
  |---|---|
  | Daily Usage | Yesterday Total Usage |
  | Last Hour Usage | Yesterday Same Hour Usage |
  | Last Hour Rainfall | Yesterday Same Hour Rainfall |
  | Last Hour Temperature | Yesterday Same Hour Temperature |
  | Last Hour Timestamp | Last Data Timestamp |
  | Meter Odometer | Lifetime Total Usage |
  | Billing Usage | Current Billing Cycle Usage |
  | Billing Cost | Estimated Billing Cost |
  | Daily Fee | Estimated Daily Cost |
  | Native Usage Unit | Meter Unit |

- **Tier fields renamed** from `tier1_gallons` / `tier1_KwH` to `tier1_units` — works for both water and electric
- **Manufacturer** corrected from `Unknown` to `Sensus Analytics`
- **`page: "null"` parameter removed** from hourly data request — sending the string `"null"` was causing intermittent 400 Bad Request errors
- **Water units** now use proper HA `UnitOfVolume` constants (`UnitOfVolume.GALLONS`, `UnitOfVolume.CENTUM_CUBIC_FEET`) to prevent HA from auto-converting gallons to liters on metric systems

### Fixed
- **Energy Dashboard fake bars** — `Yesterday Same Hour Usage` and `Yesterday Total Usage` were incorrectly set to `SensorStateClass.TOTAL`, causing HA to record yesterday's data as today's consumption. Both are now `SensorStateClass.MEASUREMENT`
- **Blocking event loop** — `requests.Session` was being used inside an async context, which blocked HA's event loop. Now fully replaced with `aiohttp`
- **Authentication cookie rejected** — `aiohttp`'s default cookie jar silently dropped session cookies from the Sensus portal. Fixed by using `aiohttp.CookieJar(unsafe=True)`
- **Missing sensor icon** — `mdi:water-clock` does not exist in HA's icon set. Replaced with `mdi:water-outline`

### Disabled by Default
The following sensors are created but disabled by default to reduce clutter. They can be enabled per entity in HA if needed:
- Meter Address
- Meter Latitude
- Meter Longitude
- Meter Unit

---

## [1.7.5] - 2025

### Water meter only
- Basic water usage sensors
- Billing cost calculation with tiered pricing
- Hourly usage data from Sensus Analytics API
- Daily usage from widget API
- Meter metadata sensors (address, coordinates, ID)
- Weather data (rainfall, temperature) from hourly API response
