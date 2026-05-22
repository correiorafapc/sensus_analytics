"""Sensor platform for the Sensus Analytics Integration."""

from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfVolume
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_NAME, DOMAIN, METER_TYPE_WATER

CF_TO_GALLON = 7.48052
CF_PER_CCF = 100


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up sensors for water or electric meter based on config entry type."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    currency = hass.config.currency
    meter_type = coordinator.meter_type

    # Shared sensors (same for both water and electric)
    shared_sensors = [
        MeterAddressSensor(coordinator, entry),
        LastReadSensor(coordinator, entry),
        MeterIdSensor(coordinator, entry),
        MeterLatitudeSensor(coordinator, entry),
        MeterLongitudeSensor(coordinator, entry),
        MeterUnitSensor(coordinator, entry),
        LastDataTimestampSensor(coordinator, entry),
        LastHourRainfallSensor(coordinator, entry),
        LastHourTemperatureSensor(coordinator, entry),
    ]

    if meter_type == METER_TYPE_WATER:
        type_sensors = [
            WaterYesterdayTotalUsageSensor(coordinator, entry),
            WaterLastHourUsageSensor(coordinator, entry),
            WaterLifetimeTotalUsageSensor(coordinator, entry),
            WaterBillingUsageSensor(coordinator, entry),
            WaterBillingCostSensor(coordinator, entry, currency),
            WaterEstimatedDailyCostSensor(coordinator, entry, currency),
        ]
    else:
        type_sensors = [
            ElectricYesterdayTotalUsageSensor(coordinator, entry),
            ElectricLastHourUsageSensor(coordinator, entry),
            ElectricLifetimeTotalUsageSensor(coordinator, entry),
            ElectricBillingUsageSensor(coordinator, entry),
            ElectricBillingCostSensor(coordinator, entry, currency),
            ElectricEstimatedDailyCostSensor(coordinator, entry, currency),
        ]

    async_add_entities(shared_sensors + type_sensors, True)


# ---------------------------------------------------------------------------
# Mixins and base classes
# ---------------------------------------------------------------------------

class WaterConversionMixin:
    """Mixin for water usage unit conversion."""

    def _convert_usage(self, usage, usage_unit=None):
        """Convert water usage to configured unit."""
        if usage is None:
            return None
        if usage_unit is None:
            usage_unit = self.coordinator.data.get("usageUnit")
        config_unit = self.coordinator.config_entry.data.get("unit_type")
        try:
            usage_float = float(usage)
        except (ValueError, TypeError):
            return None

        if usage_unit == "CF" and config_unit == "gal":
            return round(usage_float * CF_TO_GALLON)
        if usage_unit == "CF" and config_unit == "CCF":
            return round(usage_float / CF_PER_CCF, 2)
        if usage_unit == "GAL" and config_unit == "gal":
            return usage
        if usage_unit == "GAL" and config_unit == "CCF":
            return round(usage_float / CF_TO_GALLON / CF_PER_CCF, 2)
        return usage

    def _get_usage_unit(self):
        """Return the display unit for water usage using HA UnitOfVolume constants."""
        config_unit = self.coordinator.config_entry.data.get("unit_type")
        if config_unit == "gal":
            return UnitOfVolume.GALLONS
        if config_unit == "CCF":
            return UnitOfVolume.CENTUM_CUBIC_FEET
        native = self.coordinator.data.get("usageUnit", "")
        if native.upper() == "GAL":
            return UnitOfVolume.GALLONS
        return native


class ElectricConversionMixin:
    """Mixin for electric usage unit conversion."""

    def _convert_usage(self, usage, usage_unit=None):
        """Return usage as-is (kWh needs no conversion)."""
        return usage

    def _get_usage_unit(self):
        """Return kWh as the display unit."""
        return "kWh"


class SensorBase(CoordinatorEntity, SensorEntity):
    """Base class for all Sensus Analytics sensors."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor base."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._unique_id = f"{DOMAIN}_{entry.entry_id}"
        meter_label = "Water Meter" if coordinator.meter_type == METER_TYPE_WATER else "Electric Meter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Sensus Analytics",
            model=meter_label,
        )


class WaterSensorBase(WaterConversionMixin, SensorBase):
    """Base class for water sensors with dynamic units."""

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._get_usage_unit()


class ElectricSensorBase(ElectricConversionMixin, SensorBase):
    """Base class for electric sensors."""

    @property
    def native_unit_of_measurement(self):
        """Return kWh."""
        return self._get_usage_unit()


# ---------------------------------------------------------------------------
# Shared sensors (used by both water and electric)
# ---------------------------------------------------------------------------

class MeterAddressSensor(SensorBase):
    _attr_entity_registry_enabled_default = False
    """Service address associated with the meter."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Meter Address"
        self._attr_unique_id = f"{self._unique_id}_meter_address"
        self._attr_icon = "mdi:map-marker"

    @property
    def native_value(self):
        return self.coordinator.data.get("meterAddress1")


class LastReadSensor(SensorBase):
    """Timestamp of the last meter read received by the utility."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Last Read"
        self._attr_unique_id = f"{self._unique_id}_last_read"
        self._attr_icon = "mdi:clock-time-nine"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        last_read_ts = self.coordinator.data.get("lastRead")
        if last_read_ts:
            try:
                return dt_util.utc_from_timestamp(last_read_ts / 1000)
            except (ValueError, TypeError):
                return None
        return None


class MeterIdSensor(SensorBase):
    """Unique identifier of the physical meter."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Meter ID"
        self._attr_unique_id = f"{self._unique_id}_meter_id"
        self._attr_icon = "mdi:identifier"

    @property
    def native_value(self):
        return self.coordinator.data.get("meterId")


class MeterLatitudeSensor(SensorBase):
    _attr_entity_registry_enabled_default = False
    """Latitude coordinate of the meter location."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Meter Latitude"
        self._attr_unique_id = f"{self._unique_id}_meter_latitude"
        self._attr_icon = "mdi:latitude"
        self._attr_native_unit_of_measurement = "°"

    @property
    def native_value(self):
        return self.coordinator.data.get("meterLat")


class MeterLongitudeSensor(SensorBase):
    _attr_entity_registry_enabled_default = False
    """Longitude coordinate of the meter location."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Meter Longitude"
        self._attr_unique_id = f"{self._unique_id}_meter_longitude"
        self._attr_icon = "mdi:longitude"
        self._attr_native_unit_of_measurement = "°"

    @property
    def native_value(self):
        return self.coordinator.data.get("meterLong")


class MeterUnitSensor(SensorBase):
    _attr_entity_registry_enabled_default = False
    """Native unit of measurement reported by the meter."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Meter Unit"
        self._attr_unique_id = f"{self._unique_id}_usage_unit"

    @property
    def native_value(self):
        return self.coordinator.data.get("usageUnit")


class LastDataTimestampSensor(SensorBase):
    """Timestamp of the most recent hourly data point available."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Last Data Timestamp"
        self._attr_unique_id = f"{self._unique_id}_last_hour_timestamp"
        self._attr_icon = "mdi:clock-time-nine"

    @property
    def native_value(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now = datetime.now(local_tz)
        target_hour = now.hour
        hourly_data = self.coordinator.data.get("hourly_usage_data", [])
        if not hourly_data:
            return None
        for entry in hourly_data:
            entry_time = dt_util.utc_from_timestamp(entry["timestamp"] / 1000).astimezone(local_tz)
            if entry_time.hour == target_hour:
                return entry_time.strftime("%Y-%m-%d %H:%M:%S")
        return None


class LastHourRainfallSensor(SensorBase):
    """Rainfall recorded yesterday at the same hour as now."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Yesterday Same Hour Rainfall"
        self._attr_unique_id = f"{self._unique_id}_last_hour_rainfall"
        self._attr_icon = "mdi:weather-rainy"
        self._attr_native_unit_of_measurement = "in"

    @property
    def native_value(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        target_hour = datetime.now(local_tz).hour
        hourly_data = self.coordinator.data.get("hourly_usage_data", [])
        if not hourly_data:
            return None
        for entry in hourly_data:
            entry_time = dt_util.utc_from_timestamp(entry["timestamp"] / 1000).astimezone(local_tz)
            if entry_time.hour == target_hour:
                return entry["rain"]
        return None


class LastHourTemperatureSensor(SensorBase):
    """Temperature recorded yesterday at the same hour as now."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        prefix = "Water" if coordinator.meter_type == METER_TYPE_WATER else "Electric"
        self._attr_name = f"{DEFAULT_NAME} {prefix} Yesterday Same Hour Temperature"
        self._attr_unique_id = f"{self._unique_id}_last_hour_temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = "°F"

    @property
    def native_value(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        target_hour = datetime.now(local_tz).hour
        hourly_data = self.coordinator.data.get("hourly_usage_data", [])
        if not hourly_data:
            return None
        for entry in hourly_data:
            entry_time = dt_util.utc_from_timestamp(entry["timestamp"] / 1000).astimezone(local_tz)
            if entry_time.hour == target_hour:
                return entry["temp"]
        return None


# ---------------------------------------------------------------------------
# Water-specific sensors
# ---------------------------------------------------------------------------

class WaterYesterdayTotalUsageSensor(WaterSensorBase):
    """Today's total water usage from the widget API (updates throughout the day)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Water Daily Usage"
        self._attr_unique_id = f"{self._unique_id}_daily_usage"
        self._attr_icon = "mdi:water"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self._convert_usage(self.coordinator.data.get("dailyUsage"))


class WaterLastHourUsageSensor(WaterSensorBase):
    """Water usage from yesterday at the same hour as now."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Water Yesterday Same Hour Usage"
        self._attr_unique_id = f"{self._unique_id}_last_hour_usage"
        self._attr_icon = "mdi:water-outline"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        target_hour = datetime.now(local_tz).hour
        hourly_data = self.coordinator.data.get("hourly_usage_data", [])
        if not hourly_data:
            return None
        for entry in hourly_data:
            entry_time = dt_util.utc_from_timestamp(entry["timestamp"] / 1000).astimezone(local_tz)
            if entry_time.hour == target_hour:
                return self._convert_usage(entry["usage"], entry.get("usage_unit"))
        return None


class WaterLifetimeTotalUsageSensor(WaterSensorBase):
    """Lifetime total water usage recorded by the meter (never resets)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Water Lifetime Total Usage"
        self._attr_unique_id = f"{self._unique_id}_meter_odometer"
        self._attr_icon = "mdi:water"
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_suggested_unit_of_measurement = UnitOfVolume.GALLONS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        return self._convert_usage(self.coordinator.data.get("latestReadUsage"))


class WaterBillingUsageSensor(WaterSensorBase):
    """Total water usage accumulated in the current billing cycle."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Water Current Billing Cycle Usage"
        self._attr_unique_id = f"{self._unique_id}_billing_usage"
        self._attr_icon = "mdi:water"
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_suggested_unit_of_measurement = UnitOfVolume.GALLONS
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now = datetime.now(local_tz)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @property
    def native_value(self):
        return self._convert_usage(self.coordinator.data.get("billingUsage"))


class WaterBillingCostSensor(SensorBase):
    """Estimated cost for the current water billing cycle."""

    def __init__(self, coordinator, entry, currency):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Water Estimated Billing Cost"
        self._attr_unique_id = f"{self._unique_id}_billing_cost"
        self._attr_icon = "mdi:currency-usd"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = currency
        self._mixin = WaterConversionMixin()
        self._mixin.coordinator = coordinator

    @property
    def native_value(self):
        usage = self.coordinator.data.get("billingUsage")
        if usage is None:
            return None
        usage_converted = self._mixin._convert_usage(usage)
        return self._calculate_cost(usage_converted)

    def _calculate_cost(self, usage):
        d = self.coordinator.config_entry.data
        t1_limit = d.get("tier1_units") or 0
        t1_price = d.get("tier1_price", 0)
        t2_limit = d.get("tier2_units") or 0
        t2_price = d.get("tier2_price") or 0
        t3_price = d.get("tier3_price") or 0
        service_fee = d.get("service_fee", 0)
        return round(service_fee + _tiered_cost(usage, t1_limit, t1_price, t2_limit, t2_price, t3_price), 2)


class WaterEstimatedDailyCostSensor(SensorBase):
    """Estimated water cost for yesterday."""

    def __init__(self, coordinator, entry, currency):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Water Estimated Daily Cost"
        self._attr_unique_id = f"{self._unique_id}_daily_fee"
        self._attr_icon = "mdi:currency-usd"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = currency
        self._mixin = WaterConversionMixin()
        self._mixin.coordinator = coordinator

    @property
    def native_value(self):
        usage = self.coordinator.data.get("dailyUsage")
        if usage is None:
            return None
        usage_converted = self._mixin._convert_usage(usage)
        d = self.coordinator.config_entry.data
        t1_limit = d.get("tier1_units") or 0
        t1_price = d.get("tier1_price", 0)
        t2_limit = d.get("tier2_units") or 0
        t2_price = d.get("tier2_price") or 0
        t3_price = d.get("tier3_price") or 0
        return round(_tiered_cost(usage_converted, t1_limit, t1_price, t2_limit, t2_price, t3_price), 2)


# ---------------------------------------------------------------------------
# Electric-specific sensors
# ---------------------------------------------------------------------------

class ElectricYesterdayTotalUsageSensor(ElectricSensorBase):
    """Today's total electricity usage from the widget API (updates throughout the day)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Electric Daily Usage"
        self._attr_unique_id = f"{self._unique_id}_daily_usage"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self._convert_usage(self.coordinator.data.get("dailyUsage"))



class ElectricLastHourUsageSensor(ElectricSensorBase):
    """Electricity usage from yesterday at the same hour as now."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Electric Yesterday Same Hour Usage"
        self._attr_unique_id = f"{self._unique_id}_last_hour_usage"
        self._attr_icon = "mdi:lightning-bolt-outline"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        target_hour = datetime.now(local_tz).hour
        hourly_data = self.coordinator.data.get("hourly_usage_data", [])
        if not hourly_data:
            return None
        for entry in hourly_data:
            entry_time = dt_util.utc_from_timestamp(entry["timestamp"] / 1000).astimezone(local_tz)
            if entry_time.hour == target_hour:
                return self._convert_usage(entry["usage"])
        return None


class ElectricLifetimeTotalUsageSensor(ElectricSensorBase):
    """Lifetime total electricity usage recorded by the meter (never resets)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Electric Lifetime Total Usage"
        self._attr_unique_id = f"{self._unique_id}_meter_odometer"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        return self._convert_usage(self.coordinator.data.get("latestReadUsage"))


class ElectricBillingUsageSensor(ElectricSensorBase):
    """Total electricity usage accumulated in the current billing cycle."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Electric Current Billing Cycle Usage"
        self._attr_unique_id = f"{self._unique_id}_billing_usage"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self):
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now = datetime.now(local_tz)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @property
    def native_value(self):
        return self._convert_usage(self.coordinator.data.get("billingUsage"))


class ElectricBillingCostSensor(SensorBase):
    """Estimated cost for the current electricity billing cycle."""

    def __init__(self, coordinator, entry, currency):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Electric Estimated Billing Cost"
        self._attr_unique_id = f"{self._unique_id}_billing_cost"
        self._attr_icon = "mdi:currency-usd"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = currency

    @property
    def native_value(self):
        usage = self.coordinator.data.get("billingUsage")
        if usage is None:
            return None
        d = self.coordinator.config_entry.data
        t1_limit = d.get("tier1_units") or 0
        t1_price = d.get("tier1_price", 0)
        t2_limit = d.get("tier2_units") or 0
        t2_price = d.get("tier2_price") or 0
        t3_price = d.get("tier3_price") or 0
        service_fee = d.get("service_fee", 0)
        return round(service_fee + _tiered_cost(float(usage), t1_limit, t1_price, t2_limit, t2_price, t3_price), 2)


class ElectricEstimatedDailyCostSensor(SensorBase):
    """Estimated electricity cost for yesterday."""

    def __init__(self, coordinator, entry, currency):
        super().__init__(coordinator, entry)
        self._attr_name = f"{DEFAULT_NAME} Electric Estimated Daily Cost"
        self._attr_unique_id = f"{self._unique_id}_daily_fee"
        self._attr_icon = "mdi:currency-usd"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = currency

    @property
    def native_value(self):
        usage = self.coordinator.data.get("dailyUsage")
        if usage is None:
            return None
        d = self.coordinator.config_entry.data
        t1_limit = d.get("tier1_units") or 0
        t1_price = d.get("tier1_price", 0)
        t2_limit = d.get("tier2_units") or 0
        t2_price = d.get("tier2_price") or 0
        t3_price = d.get("tier3_price") or 0
        return round(_tiered_cost(float(usage), t1_limit, t1_price, t2_limit, t2_price, t3_price), 2)


# ---------------------------------------------------------------------------
# Shared tier pricing helper
# ---------------------------------------------------------------------------

def _tiered_cost(usage, t1_limit, t1_price, t2_limit, t2_price, t3_price):
    """Calculate tiered cost given usage and tier configuration."""
    if usage is None:
        return 0
    try:
        usage = float(usage)
    except (ValueError, TypeError):
        return 0

    if t1_limit == 0:
        return usage * t1_price
    if t2_limit == 0:
        if usage <= t1_limit:
            return usage * t1_price
        return t1_limit * t1_price + (usage - t1_limit) * t2_price
    if t3_price > 0:
        if usage <= t1_limit:
            return usage * t1_price
        if usage <= t1_limit + t2_limit:
            return t1_limit * t1_price + (usage - t1_limit) * t2_price
        return t1_limit * t1_price + t2_limit * t2_price + (usage - t1_limit - t2_limit) * t3_price
    return usage * t1_price
