"""Config flow for the Harvst irrigation control panel integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HarvstApiError, HarvstAuthError, HarvstClient
from .const import CONF_ZONE_RUNTIME, DEFAULT_ZONE_MAX_RUNTIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def _validate_and_get_device_id(hass, data: dict[str, Any]) -> str:
    session = async_get_clientsession(hass)
    client = HarvstClient(
        session,
        data[CONF_HOST],
        data.get(CONF_USERNAME) or None,
        data.get(CONF_PASSWORD) or None,
    )
    await client.async_test_connection()
    info = await client.async_get_device_info()
    return info["device_id"]


class HarvstConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Harvst."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_id = await _validate_and_get_device_id(self.hass, user_input)
            except HarvstAuthError:
                errors["base"] = "invalid_auth"
            except HarvstApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Harvst connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=f"Harvst ({user_input[CONF_HOST]})", data=user_input
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Let an existing entry's host/credentials be updated (e.g. the panel's IP changed)."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                device_id = await _validate_and_get_device_id(self.hass, user_input)
            except HarvstAuthError:
                errors["base"] = "invalid_auth"
            except HarvstApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Harvst connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                # Reconfigure is for pointing the *same* panel at a new address,
                # not swapping in a different one - a mismatched device ID here
                # means this isn't the panel this entry was originally set up for.
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(reconfigure_entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HarvstOptionsFlow:
        return HarvstOptionsFlow(config_entry)


def _connection_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_HOST: data.get(CONF_HOST, ""),
        CONF_USERNAME: data.get(CONF_USERNAME, ""),
        CONF_PASSWORD: data.get(CONF_PASSWORD, ""),
    }


class HarvstOptionsFlow(OptionsFlow):
    """Connection details (host/credentials) plus the zone safety cutoff.

    Connection details normally belong in a reconfigure flow rather than
    options, but that lives behind an easy-to-miss menu item, so it's
    surfaced here too - this is what most people actually click "Configure"
    expecting to find.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        entry = self._config_entry

        if user_input is not None:
            new_connection = _connection_fields(user_input)
            if new_connection != _connection_fields(entry.data):
                try:
                    device_id = await _validate_and_get_device_id(self.hass, new_connection)
                except HarvstAuthError:
                    errors["base"] = "invalid_auth"
                except HarvstApiError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error validating Harvst connection")
                    errors["base"] = "unknown"
                else:
                    if device_id != entry.unique_id:
                        errors["base"] = "wrong_device"
                    else:
                        self.hass.config_entries.async_update_entry(entry, data=new_connection)

            if not errors:
                return self.async_create_entry(
                    title="", data={CONF_ZONE_RUNTIME: user_input[CONF_ZONE_RUNTIME]}
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required(CONF_ZONE_RUNTIME): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=7200)
                ),
            }
        )
        suggested = user_input or {
            **_connection_fields(entry.data),
            CONF_ZONE_RUNTIME: entry.options.get(CONF_ZONE_RUNTIME, DEFAULT_ZONE_MAX_RUNTIME),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )
