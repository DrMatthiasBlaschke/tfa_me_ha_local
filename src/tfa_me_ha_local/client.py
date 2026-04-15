"""TFA.me library for Home Assistant: client.py."""


import asyncio
import json
import logging
import socket
from typing import Any
import aiohttp

from .exceptions import (
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
    TFAmeException,
    TFAmeConnectionError,
)

# Debugging
_LOGGER = logging.getLogger(__name__)



class TFAmeClient:
    """Simple client to fetch sensor data from a TFA.me station."""

    def __init__(
        self,
        host: str,
        path: str = "sensors",
        timeout: int = 5,
        session: aiohttp.ClientSession | None = None,
        log_level: int = 0,
        close_session: bool = False
    ):
        """Initialize the TFA.me client.

        Args:
            host: IP address or hostname of the station.
            path: Endpoint path (default: "sensors").
            timeout: Timeout time to establish a connection
            session: Optional aiohttp.ClientSession. If not provided, a new one will be created and closed automatically.
            log_level: Log level for debug output.
            close_session: Close session after fetching data
        """
        self._host = host
        self._path = path
        self._timeout = timeout
        self._session = session
        self._data: dict = {}
        self._log_level = log_level
        self._close_session = close_session

    async def async_get_sensors(self) -> dict:
        """Fetch sensor data from the gateway.

        Raises:
            TFAmeTimeoutError: Request timed out.
            TFAmeConnectionError: Network or DNS issue.
            TFAmeHTTPError: Non-200 HTTP status code.
            TFAmeJSONError: Response was not valid JSON.
            TFAmeException: Any other unexpected error.

        Returns:
            Parsed JSON data as a dictionary.
        """
        url = f"http://{self._host}/{self._path}"
        if self._log_level >= 1:
            # Show the URL to the device
            msg: str = "Request URL '" + url + "'"
            _LOGGER.info(msg)

        # 
        session: aiohttp.ClientSession | None = self._session

        try:
             # Reuse provided session or create a new temporary one
            if session is None:
                session = aiohttp.ClientSession()
                self._session = session
     
            async with asyncio.timeout(self._timeout):
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise TFAmeHTTPError(f"HTTP error: {resp.status}")
                    try:
                        data = await resp.json()
                    except aiohttp.ContentTypeError as err:
                        raise TFAmeJSONError(f"Invalid JSON response: {err}") from err

                    if self._log_level >= 2:
                        _LOGGER.debug(
                            "TFAmeClient received data:\n%s", json.dumps(data, indent=2)
                        )
                    self._data = data
                    return data

        except asyncio.TimeoutError as err:
            raise TFAmeTimeoutError("Request to TFA.me sation timed out") from err
        except aiohttp.ClientConnectorError as err:
            raise TFAmeConnectionError(f"Connection error: {err}") from err
        except socket.gaierror as err:
            raise TFAmeConnectionError(f"DNS resolution failed: {err}") from err
        except TFAmeException:
            # Re-raise any already wrapped TFAmeException
            raise
        except Exception as err:
            raise TFAmeException(f"Unexpected error: {err}") from err
        finally:
            # Only close the session if we created it in this method
            if self._close_session and session is not None:
                if self._log_level >= 1:
                    _LOGGER.debug("Close session")

                await session.close()

    async def close(self) -> None:
        """Close open client session."""
        if self._session:
            await self._session.close()

    async def __aenter__(self) -> Any:
        """Async enter, retrun the TFAmeClient object."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit.
        Args:
        ----
            _exc_info: Exec type.
        """
        if self._log_level >= 1:
            _LOGGER.debug("Close session")

        await self.close()


    def parse_and_filter_json(
        self, json_data: dict[str, Any], valid_keys: list[str],
    ) -> tuple[dict[str, dict[str, Any]], str, str]:
        """Parse a TFA.me station/gateway JSON dictionary to get TFAmeCoordinatorData values for coordinator.

        Args:
            json_data: JSON data from station/gateway
            valid_keys: list with valid measurement keys

        Raises:
            TFAmeJSONError: JSON data from station/gateway was not valid.
 
        Returns:
            filtered_list: Filtered entity list
            gateway_id: Gateway/station ID
            gateway_sw: Gateway/station SW number
        """

        filtered_list: dict[
            str, dict[str, Any]
        ] = {}  # fitered list/dict with unique IDs & measurement data, units, etc.

        try:
            # Get gateway ID, SW version & sensor list
            gateway_id = str(json_data.get("gateway_id", "tfame")).lower()
            gateway_sw = str(json_data.get("gateway_sw", "?"))
            sensors = json_data.get("sensors", [])

            for sensor in sensors:
                sensor_id = sensor["sensor_id"]

                for m_name, values in sensor.get("measurements", {}).items():
                    # if measurement_in_list(s = m_name, m_list = valid_keys):
                    if m_name in valid_keys:
                        # Unique ID build of "unique station/gateway ID" & "unique sensor ID"  & measurement name
                        # (IDs set while production process)
                        unique_id = f"sensor.{gateway_id}_{sensor_id}_{m_name}"

                        # Minimum base data for all entities: value, unit, ts (timestamp)
                        base = {
                            "value": values["value"],  # Measurement value
                            "unit": values["unit"], # Measurement unit
                            "ts": sensor["ts"],  # UTC reception time stamp in seconds
                        }
                        filtered_list[unique_id] = base

                        # Special cases
                        # Wind direction: create extra entity for degrees
                        if m_name == "wind_direction":
                            deg_id = f"{unique_id}_deg"
                            filtered_list[deg_id] = {
                                **base,
                                "unit": "°",
                            }

                        # Rain: create extra entity relative, 1 hour, 24 hours
                        if m_name == "rain":
                            # relative
                            filtered_list[f"{unique_id}_rel"] = {
                                **base,
                                "reset_rain": False,
                            }

                            # 1 hour rain
                            filtered_list[f"{unique_id}_1_hour"] = {
                                **base,
                                "reset_rain": False,
                            }

                            # 24 hours rain
                            filtered_list[f"{unique_id}_24_hours"] = {
                                **base,
                                "reset_rain": False,
                            }

        except Exception as err:
            raise TFAmeJSONError(f"Invalid JSON response: {err}") from err
        else:
            return filtered_list, gateway_id, gateway_sw

