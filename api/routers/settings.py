from fastapi import APIRouter, HTTPException
from loguru import logger

from api.models import SettingsResponse, SettingsUpdate
from open_notebook.domain.content_settings import ContentSettings
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


def _safe_string(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _safe_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get all application settings."""
    try:
        settings: ContentSettings = await ContentSettings.get_instance()  # type: ignore[assignment]

        return SettingsResponse(
            default_content_processing_engine_doc=_safe_string(
                settings.default_content_processing_engine_doc, "auto"
            ),
            default_content_processing_engine_url=_safe_string(
                settings.default_content_processing_engine_url, "auto"
            ),
            default_embedding_option=_safe_string(
                settings.default_embedding_option, "ask"
            ),
            auto_delete_files=_safe_string(settings.auto_delete_files, "yes"),
            youtube_preferred_languages=_safe_string_list(
                settings.youtube_preferred_languages
            ),
        )
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Error fetching settings"
        )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(settings_update: SettingsUpdate):
    """Update application settings."""
    try:
        settings: ContentSettings = await ContentSettings.get_instance()  # type: ignore[assignment]

        # Update only provided fields
        if settings_update.default_content_processing_engine_doc is not None:
            # Cast to proper literal type
            from typing import Literal, cast

            settings.default_content_processing_engine_doc = cast(
                Literal["auto", "docling", "simple"],
                settings_update.default_content_processing_engine_doc,
            )
        if settings_update.default_content_processing_engine_url is not None:
            from typing import Literal, cast

            settings.default_content_processing_engine_url = cast(
                Literal["auto", "firecrawl", "jina", "simple"],
                settings_update.default_content_processing_engine_url,
            )
        if settings_update.default_embedding_option is not None:
            from typing import Literal, cast

            settings.default_embedding_option = cast(
                Literal["ask", "always", "never"],
                settings_update.default_embedding_option,
            )
        if settings_update.auto_delete_files is not None:
            from typing import Literal, cast

            settings.auto_delete_files = cast(
                Literal["yes", "no"], settings_update.auto_delete_files
            )
        if settings_update.youtube_preferred_languages is not None:
            settings.youtube_preferred_languages = (
                settings_update.youtube_preferred_languages
            )

        await settings.update()

        return SettingsResponse(
            default_content_processing_engine_doc=_safe_string(
                settings.default_content_processing_engine_doc, "auto"
            ),
            default_content_processing_engine_url=_safe_string(
                settings.default_content_processing_engine_url, "auto"
            ),
            default_embedding_option=_safe_string(
                settings.default_embedding_option, "ask"
            ),
            auto_delete_files=_safe_string(settings.auto_delete_files, "yes"),
            youtube_preferred_languages=_safe_string_list(
                settings.youtube_preferred_languages
            ),
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Error updating settings"
        )
