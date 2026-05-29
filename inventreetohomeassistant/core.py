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
    VERSION = "3.0.0"

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
        """Check description for tag_id and call HA drawcustom directly."""
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

        url = f"{ha_url}/api/services/open_epaper_link/drawcustom"
        headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "rotate": 0,
            "dither": "0",
            "ttl": 60,
            "refresh_type": "0",
            "dry-run": False,
            "background": "white",
            "payload": [
                {
                    "type": "dlimg",
                    "url": "https://www.healthclusterportugal.pt/media/uploads/2022/06/30/FraunhoferPortugal_i3T72fk.png.768x768_q95_upscale.png",
                    "x": 4,
                    "y": 4,
                    "xsize": 40,
                    "ysize": 40,
                    "rotate": 0,
                },
                {
                    "type": "text",
                    "value": drawer_title,
                    "x": 4,
                    "y": 55,
                    "anchor": "lm",
                    "size": 18,
                    "color": "black",
                    "font": "ppb.ttf",
                },
                {
                    "type": "qrcode",
                    "data": str(location_id),
                    "x": 170,
                    "y": 4,
                    "boxsize": 3,
                    "border": 1,
                    "color": "black",
                    "bgcolor": "white",
                },
            ],
            "target": {
                "device_id": device_id,
            },
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            print(f"[HA Plugin] Sent drawcustom for '{drawer_title}' (device: {device_id})")
        except requests.RequestException as e:
            print(f"[HA Plugin] Failed to call drawcustom: {e}")