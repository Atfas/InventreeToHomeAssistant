"""Small plugin to send data to HA when certain sublocations are updated on Inventree"""

import requests
from plugin import InvenTreePlugin
from plugin.mixins import EventMixin, SettingsMixin


class InventreeToHomeAssistant(EventMixin, SettingsMixin, InvenTreePlugin):
    """InventreeToHomeAssistant - custom InvenTree plugin."""

    TITLE = "InventreeToHomeAssistant"
    NAME = "InventreeToHomeAssistant"
    SLUG = "inventreetohomeassistant"
    DESCRIPTION = "Send data to HA when a sublocation name is updated on InvenTree"
    VERSION = "2.2.0"

    AUTHOR = "Afonso Saraiva, Daniel Marques, Inês Francisco, Hugo Silva"
    WEBSITE = "https://inventreetohomeassistant.com"
    LICENSE = "MIT"
    PUBLISH_DATE = "2026-05-29"

    MAX_LINE_LENGTH = 11

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
            "default": "",
        },
    }

    def format_title(self, name: str) -> str:
        """
        Format a location name for display on a small e-paper tag.
        - If <= MAX_LINE_LENGTH chars: use as-is
        - If it has spaces: break at spaces so each line <= MAX_LINE_LENGTH
        - If it's one long word: truncate with '...' at MAX_LINE_LENGTH
        """
        if len(name) <= self.MAX_LINE_LENGTH:
            return name

        words = name.split(" ")

        # Single word too long — truncate
        if len(words) == 1:
            return name[: self.MAX_LINE_LENGTH - 3] + "..."

        # Multiple words — pack words into lines greedily
        lines = []
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= self.MAX_LINE_LENGTH:
                current += " " + word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)

        return "\n".join(lines)

    def wants_process_event(self, event: str) -> bool:
        """Only process StockLocation save events."""
        return event == "stock_stocklocation.saved"

    def process_event(self, event: str, *args, **kwargs) -> None:
        """Check description for tag_id and trigger HA automation."""
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

        device_id = description[len("tag_id:"):].strip()
        drawer_title = self.format_title(location.name)

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
                "drawer_title": drawer_title,
                "qr_text": str(location_id),
            },
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            print(f"[HA Plugin] Triggered automation for '{location_id}' on '{drawer_title}' (device: {device_id})")
        except requests.RequestException as e:
            print(f"[HA Plugin] Failed to trigger HA automation: {e}")