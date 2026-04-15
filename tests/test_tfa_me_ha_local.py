"""TFA.me library for Home Assistant: test_tfa_me_ha_local.py."""

import datetime
import json
import logging
import asyncio
from typing import Any
from tfa_me_ha_local.client import TFAmeClient
from tfa_me_ha_local.exceptions import TFAmeException
from tfa_me_ha_local.history import SensorHistory
from tfa_me_ha_local.validators import TFAmeValidator

_LOGGER = logging.getLogger(__name__)

# Valid keys for creating entities
VALID_KEYS = [
    "temperature",
    "temperature_probe",
    "humidity",
    "co2",
    "barometric_pressure",
    "rssi",
    "lowbatt",
    "wind_direction",
    "wind_speed",
    "wind_gust",
    "rain",
]

async def main() -> None:
    "Test some connections to real TFA.me devices."
    
    json_data = {}  # Original JSON data for station/gateway
    parsed_list: dict[str, dict[str, Any]] = {} # Created entity list
    parsed_gateway_id : str # Station/gateway ID
    parsed_gateway_sw : str # Station/gateway SW number

  
    # Test A: Use valid IP and path
   
    # 1. Create client
    tfa_me_client = TFAmeClient("192.168.1.60", "sensors", timeout=7, log_level=1)
    
    # 2. Request JSON data from station/gateway 
    json_data = await tfa_me_client.async_get_sensors()
    
    # 3. Parse data and create TFA.me varaiables
    parsed_list, parsed_gateway_id, parsed_gateway_sw = tfa_me_client.parse_and_filter_json(json_data=json_data, valid_keys=VALID_KEYS) 

    _LOGGER.info("TFA.me station ID: '%s'", parsed_gateway_id)
    _LOGGER.info("TFA.me SW version: '%s'", parsed_gateway_sw)
    _LOGGER.info("TFA.me data:\n'%s'", json.dumps(parsed_list, indent=2))

    # Test B: Use not existing IP 
    await client_test("192.168.1.35", "sensors")

    # Test C: Use wrong path/URL
    await client_test("192.168.1.36", "xxx")


async def client_test(host: str, path: str, timeout: int = 5) -> None:
    """Test a client connection to a TFA.me device."""
    msg = f"Test connection to '{host}/{path}' ....."
    _LOGGER.info(msg)

    try:
        tfa_me_client = TFAmeClient(host, path, timeout=timeout, log_level=1)
        data = await tfa_me_client.async_get_sensors()
        if not data:
            _LOGGER.error("Error, no data")
            return None
        else:
            _LOGGER.info("Data:\n'%s'", json.dumps(data, indent=2))
            return data
    except TFAmeException as err:
        _LOGGER.error("Failed to fetch sensors: '%s'", err)


def test_is_valid_ip_or_tfa_me() -> None:
    """Test is_valid_ip_or_tfa_me() for class TFAmeConfigFlow."""

    validator = TFAmeValidator()
    # Valid IP
    assert validator.is_valid_ip_or_tfa_me("192.168.1.1")

    # Valid mDNS
    assert validator.is_valid_ip_or_tfa_me("012-345-678")

    # Invalid Host/IP
    assert not validator.is_valid_ip_or_tfa_me(42)

def test_history_class() -> None:
    """Test history class."""
    hist = SensorHistory(2)  # 2 minutes (120 seconds) history
    # test list empty
    assert hist.get_oldest_and_newest() == (None, None)

    now = int(datetime.now().timestamp())
    hist.add_measurement(12.1, now - 180)  # to old, will be reoved
    hist.add_measurement(12.1, now - 120)
    # test get list with one tuple
    assert hist.get_data() == [(12.1, now - 120)]

    hist.add_measurement(12.4, now - 60)
    hist.add_measurement(12.7, now)

    # test get oldest newest
    assert hist.get_oldest_and_newest() == ((12.1, now - 120), (12.7, now))

# Main entry point
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

