import dataclasses


@dataclasses.dataclass
class DeviceListInfo:
    flags: int
    type: int
    id: int
    loc_id: int
    serial: str
    description: str
    handle: int
