"""Small plugin to send data to HA when certain sublocations are updated on Inventree"""

import requests
from plugin import InvenTreePlugin
from plugin.mixins import EventMixin, SettingsMixin
from . import PLUGIN_VERSION


class InventreeToHomeAssistant(EventMixin, SettingsMixin, InvenTreePlugin):
    """InventreeToHomeAssistant - custom InvenTree plugin."""

    TITLE = "InventreeToHomeAssistant"
    NAME = "InventreeToHomeAssistant"
    SLUG = "inventreetohomeassistant"
    DESCRIPTION = "Send data to HA when a sublocation name is updated on InvenTree"
    VERSION = PLUGIN_VERSION

    AUTHOR = "Afonso Saraiva, Daniel Marques, Inês Francisco, Hugo Silva"
    WEBSITE = "https://inventreetohomeassistant.com"
    LICENSE = "MIT"

    SETTINGS = {
        "HA_URL": {
            "name": "Home Assistant URL",
            "description": "Base URL of your Home Assistant instance (e.g. http://homeassistant.local:8123)",
            "default": "",
        },
        "HA_TOKEN": {
            "name": "Long-Lived Access Token",
            "description": "Bearer token for Home Assistant API authentication",
            "default": "",
        },
        "HA_AUTOMATION_ENTITY": {
            "name": "Automation Entity ID",
            "description": "The HA automation entity to trigger (e.g. automation.inventree_gaveta_update)",
            "default": "automation.inventree_gaveta_update",
        },
    }

    def wants_process_event(self, event: str) -> bool:
        """Only process StockLocation save events."""
        return event == "stock_stocklocation.saved"

    def process_event(self, event: str, *args, **kwargs) -> None:
        """Check description for tag_id and trigger HA automation with new name."""
        from stock.models import StockLocation

        location_id = kwargs.get("id")
        if location_id is None:
            return

        try:
            location = StockLocation.objects.get(pk=location_id)
        except StockLocation.DoesNotExist:
            return

        description = location.description or ""
        if not description.startswith("tag_id:"):
            return

        device_id = description[len("tag_id:") :].strip()
        new_name = location.name

        ha_url = self.get_setting("HA_URL").rstrip("/")
        ha_token = self.get_setting("HA_TOKEN")
        entity_id = self.get_setting("HA_AUTOMATION_ENTITY")

        url = f"{ha_url}/api/services/automation/trigger"
        headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "entity_id": entity_id,
            "variables": {
                "device_id": device_id,
                "message": new_name,
            },
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            print(
                f"[HA Plugin] Triggered automation for '{new_name}' (device: {device_id})"
            )
        except requests.RequestException as e:
            print(f"[HA Plugin] Failed to trigger HA automation: {e}")
