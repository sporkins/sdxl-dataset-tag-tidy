from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.services.config_service import ConfigService
from app.services.dataset_manager import DatasetManager
from app.services.lmstudio_service import LmStudioService

config_service = ConfigService(base_dir=Path(__file__).resolve().parent.parent / "config")
dataset_manager = DatasetManager(config_service=config_service)
lm_studio_service = LmStudioService()


def get_config_service() -> ConfigService:
    return config_service


def get_dataset_manager(
    _: Annotated[ConfigService, Depends(get_config_service)]
) -> DatasetManager:
    return dataset_manager


def get_lm_studio_service() -> LmStudioService:
    return lm_studio_service
