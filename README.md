# Sensus Analytics Integration for Home Assistant

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![HACS](https://img.shields.io/badge/HACS-Custom-orange)
![License](https://img.shields.io/badge/license-MIT-green)

A Home Assistant custom integration for **Sensus Analytics** utility portals, supporting both **water** and **electric** meters. Monitor your usage, track billing costs, and integrate with the HA Energy Dashboard.

---

## Features

- 💧 **Water meter** support — usage, billing, today's consumption
- 💡 **Electric meter** support — usage, billing, hourly data
- 📊 **Energy Dashboard** compatible — plug in and go
- 💰 **Tiered billing** cost calculation (up to 3 tiers)
- 🕐 **Today Usage** sensor — persists across HA restarts
- 🌡️ **Weather data** — hourly rainfall and temperature from the API
- 🔄 Fully async — no blocking calls

---

## Requirements

- Home Assistant 2023.1.0 or newer
- A Sensus Analytics utility portal account (e.g. `my-clync.sensus-analytics.com`)

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations** → click the **⋮** menu → **Custom repositories**
3. Add `https://github.com/correiorafapc/sensus_analytics` with category **Integration**
4. Search for **Sensus Analytics** and click **Download**
5. Restart Home Assistant

### Manual

1. Download the latest release zip
2. Extract the `sensus_analytics` folder into `config/custom_components/`
3. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Sensus Analytics**
3. Fill in the form:

| Field | Description |
|---|---|
| **Meter Type** | `Water` or `Electric` |
| **Base URL** | Your portal URL (e.g. `https://my-clync.sensus-analytics.com`) |
| **Username** | Your portal login username |
| **Password** | Your portal login password |
| **Account Number** | Your utility account number |
| **Meter Number** | Your physical meter ID |
| **Unit Type** | `gal` or `CCF` for water, `kWh` for electric |
| **Tier 1–3 Units** | Tier usage limits (leave blank if not applicable) |
| **Tier 1–3 Price** | Price per unit for each tier |
| **Monthly Service Fee** | Fixed monthly charge from your utility |

> 💡 You can add the integration **twice** — once for Water and once for Electric — to monitor both meters from the same portal.

---

## Sensors

### Water Meter

| Sensor | Description | Energy Dashboard |
|---|---|---|
| Water Lifetime Total Usage | All-time odometer — never resets | ✅ Recommended |
| Water Current Billing Cycle Usage | Total usage this billing cycle | — |
| Water Daily Usage | Today's running total from the widget API | — |
| Water Yesterday Same Hour Usage | Yesterday's usage at the current hour | — |
| Water Estimated Billing Cost | Calculated cost for this billing cycle | — |
| Water Estimated Daily Cost | Calculated cost for yesterday | — |
| Water Last Read | Timestamp of last meter transmission | — |

### Electric Meter

| Sensor | Description | Energy Dashboard |
|---|---|---|
| Electric Lifetime Total Usage | All-time odometer — never resets | ✅ Recommended |
| Electric Current Billing Cycle Usage | Total usage this billing cycle | — |
| Electric Daily Usage | Today's running total from the widget API | — |
| Electric Yesterday Same Hour Usage | Yesterday's usage at the current hour | — |
| Electric Estimated Billing Cost | Calculated cost for this billing cycle | — |
| Electric Estimated Daily Cost | Calculated cost for yesterday | — |
| Electric Last Read | Timestamp of last meter transmission | — |

### Shared (both meter types)

| Sensor | Enabled by Default |
|---|---|
| Yesterday Same Hour Rainfall | ✅ |
| Yesterday Same Hour Temperature | ✅ |
| Last Data Timestamp | ✅ |
| Meter Address | ❌ Disabled |
| Meter ID | ✅ |
| Meter Latitude | ❌ Disabled |
| Meter Longitude | ❌ Disabled |
| Meter Unit | ❌ Disabled |

---

## Energy Dashboard Setup

1. Go to **Settings → Dashboards → Energy**
2. Under **Water consumption**, add **Sensus Analytics Water Lifetime Total Usage**
3. Under **Electricity grid**, add **Sensus Analytics Electric Lifetime Total Usage**

> ⚠️ Do **not** add both `Lifetime Total Usage` and `Today Usage` for the same meter — this double-counts consumption.

---

## Data Refresh

The integration polls the Sensus Analytics API every **30 minutes**. Water meter data is typically available with a 1–24 hour delay depending on your utility's meter read schedule.

---

## Troubleshooting

**Sensors showing `unavailable`**
- Verify your Base URL, username, and password in the integration options
- Check HA logs for authentication errors

**Energy Dashboard showing wrong data**
- Use only `Lifetime Total Usage` in the Energy Dashboard
- Make sure `Yesterday Same Hour Usage` and `Yesterday Total Usage` are **not** added there

**Today Usage resets unexpectedly**
- The midnight baseline is persisted to disk at `.storage/sensus_analytics_midnight_odometer_*`
- A restart shortly after midnight may cause a brief reset

---

## Contributing

Pull requests are welcome! Please open an issue first to discuss changes.

---

## License

MIT © [correiorafapc](https://github.com/correiorafapc/sensus_analytics)
