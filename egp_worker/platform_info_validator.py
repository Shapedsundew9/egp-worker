""" Platform info validator."""
from datetime import datetime
from hashlib import sha256
from json import load
from os.path import dirname, join
from typing import Any

from egp_utils.base_validator import base_validator

with open(
    join(dirname(__file__), "formats/platform_info_entry_format.json"),
    "r",
    encoding="utf-8",
) as file_ptr:
    _PLATFORM_INFO_ENTRY_SCHEMA: dict[str, Any] = load(file_ptr)


class _platform_info_validator(base_validator):
    def _check_with_valid_created(self, field, value) -> None:
        try:
            date_time_obj: datetime = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            self._error(field, "Created date-time is not valid. Unknown error parsing.")
            return

        if date_time_obj > datetime.utcnow():
            self._error(field, "Created date-time cannot be in the future.")

    def _normalize_default_setter_set_signature(self, _) -> bytes:
        sig_str: str = self.document["machine"] + self.document["processor"] + self.document["python_version"]
        sig_str += self.document["system"] + self.document["release"] + str(int(self.document["EGPOps/s"]))

        # Remove spaces etc. to give some degrees of freedom in formatting and
        # not breaking the signature
        return sha256("".join(sig_str.split()).encode()).digest()

    def _normalize_default_setter_set_created(self, _) -> str:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _coerce_string(self, value: str, length: int) -> str:
        return value[:length] if isinstance(value, str) and len(value) > length else value

    def _normalize_coerce_string_64(self, value: str) -> str:
        return self._coerce_string(value, 64)

    def _normalize_coerce_string_128(self, value: str) -> str:
        return self._coerce_string(value, 128)

    def _normalize_coerce_string_1024(self, value: str) -> str:
        return self._coerce_string(value, 1024)


platform_info_validator = _platform_info_validator(_PLATFORM_INFO_ENTRY_SCHEMA)
