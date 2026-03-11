from app.crud.base import CRUDBase
from app.models.app_version import AppVersion
from app.schemas.app_version import AppVersionCreate, AppVersionUpdate


class CRUDAppVersion(CRUDBase[AppVersion, AppVersionCreate, AppVersionUpdate]):
    pass


app_version = CRUDAppVersion(AppVersion)
