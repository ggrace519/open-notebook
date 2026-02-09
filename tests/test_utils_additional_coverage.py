from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_notebook.exceptions import DatabaseOperationError, NotFoundError
from open_notebook.utils.context_builder import (
    ContextBuilder,
    ContextConfig,
    ContextItem,
    build_mixed_context,
    build_notebook_context,
    build_source_context,
)
from open_notebook.utils.graph_utils import get_session_message_count
from open_notebook.utils.version_utils import (
    get_version_from_github,
    get_version_from_github_async,
)


class TestContextBuilderAdditional:
    def test_context_item_auto_token_count(self):
        with patch("open_notebook.utils.context_builder.token_count", return_value=17):
            item = ContextItem(id="x", type="note", content={"a": 1})
            assert item.token_count == 17

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Source")
    async def test_add_source_context_with_insights(self, mock_source_class):
        builder = ContextBuilder(include_insights=True)

        source = MagicMock()
        source.id = "source:1"
        source.get_context = AsyncMock(return_value={"id": "source:1", "title": "S"})
        source.get_insights = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="insight:1", insight_type="summary", content="hello world"
                )
            ]
        )
        mock_source_class.get = AsyncMock(return_value=source)

        await builder._add_source_context("1", "insights")

        assert len(builder.items) == 2
        assert builder.items[0].type == "source"
        assert builder.items[1].type == "insight"

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Source")
    async def test_add_source_context_full_content_no_insights(self, mock_source_class):
        builder = ContextBuilder(include_insights=False)

        source = MagicMock()
        source.id = "source:1"
        source.get_context = AsyncMock(
            return_value={"id": "source:1", "title": "S", "full_text": "abc"}
        )
        source.get_insights = AsyncMock(return_value=[])
        mock_source_class.get = AsyncMock(return_value=source)

        await builder._add_source_context("source:1", "full content")

        source.get_context.assert_awaited_once_with(context_size="long")
        assert len(builder.items) == 1

    @pytest.mark.asyncio
    async def test_add_source_context_not_in(self):
        builder = ContextBuilder()
        await builder._add_source_context("source:1", "not in")
        assert builder.items == []

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Source")
    async def test_add_source_context_not_found(self, mock_source_class):
        builder = ContextBuilder()
        mock_source_class.get = AsyncMock(side_effect=NotFoundError("missing"))
        await builder._add_source_context("source:1", "insights")
        assert builder.items == []

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Notebook")
    async def test_add_notebook_context_with_config(self, mock_notebook_class):
        config = ContextConfig(
            sources={"source:1": "insights"}, notes={"note:1": "full content"}
        )
        builder = ContextBuilder(notebook_id="notebook:1", context_config=config)
        builder._add_source_context = AsyncMock()
        builder._add_note_context = AsyncMock()

        mock_notebook_class.get = AsyncMock(return_value=MagicMock())
        await builder._add_notebook_context("notebook:1")

        builder._add_source_context.assert_awaited_once_with("source:1", "insights")
        builder._add_note_context.assert_awaited_once_with("note:1", "full content")

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Notebook")
    async def test_add_notebook_context_defaults(self, mock_notebook_class):
        builder = ContextBuilder(notebook_id="notebook:1")
        builder._add_source_context = AsyncMock()
        builder._add_note_context = AsyncMock()

        notebook = MagicMock()
        notebook.get_sources = AsyncMock(
            return_value=[SimpleNamespace(id="source:1"), SimpleNamespace(id=None)]
        )
        notebook.get_notes = AsyncMock(
            return_value=[SimpleNamespace(id="note:1"), SimpleNamespace(id=None)]
        )
        mock_notebook_class.get = AsyncMock(return_value=notebook)

        await builder._add_notebook_context("notebook:1")
        builder._add_source_context.assert_awaited_once_with("source:1", "insights")
        builder._add_note_context.assert_awaited_once_with("note:1", "full content")

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Notebook")
    async def test_add_notebook_context_missing_notebook(self, mock_notebook_class):
        builder = ContextBuilder(notebook_id="notebook:404")
        mock_notebook_class.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await builder._add_notebook_context("notebook:404")

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Note")
    async def test_add_note_context(self, mock_note_class):
        builder = ContextBuilder()
        note = MagicMock()
        note.id = "note:1"
        note.get_context = MagicMock(return_value={"id": "note:1", "content": "x"})
        mock_note_class.get = AsyncMock(return_value=note)

        await builder._add_note_context("1", "full content")
        assert len(builder.items) == 1
        assert builder.items[0].type == "note"

    @pytest.mark.asyncio
    async def test_add_note_context_not_in(self):
        builder = ContextBuilder()
        await builder._add_note_context("note:1", "not in")
        assert builder.items == []

    @pytest.mark.asyncio
    @patch("open_notebook.utils.context_builder.Note")
    async def test_add_note_context_not_found(self, mock_note_class):
        builder = ContextBuilder()
        mock_note_class.get = AsyncMock(side_effect=NotFoundError("missing"))
        await builder._add_note_context("note:1", "full content")
        assert builder.items == []

    @pytest.mark.asyncio
    async def test_build_success_and_metadata(self):
        builder = ContextBuilder(
            source_id="source:1", notebook_id="notebook:1", max_tokens=5
        )

        async def add_source(_source_id):
            builder.add_item(
                ContextItem(id="s1", type="source", content={"a": "b"}, token_count=2)
            )

        async def add_notebook(_notebook_id):
            builder.add_item(
                ContextItem(id="n1", type="note", content={"a": "c"}, token_count=2)
            )

        builder._add_source_context = add_source
        builder._add_notebook_context = add_notebook
        builder._process_custom_params = AsyncMock()

        result = await builder.build()
        assert result["total_items"] == 2
        assert "metadata" in result
        assert result["notebook_id"] == "notebook:1"

    @pytest.mark.asyncio
    async def test_build_wraps_errors(self):
        builder = ContextBuilder(source_id="source:1")
        builder._add_source_context = AsyncMock(side_effect=Exception("boom"))
        with pytest.raises(DatabaseOperationError):
            await builder.build()

    def test_prioritize_truncate_dedup_and_format(self):
        builder = ContextBuilder(max_tokens=4)
        builder.items = [
            ContextItem(
                id="a", type="note", content={"x": 1}, priority=10, token_count=3
            ),
            ContextItem(
                id="a", type="note", content={"x": 2}, priority=9, token_count=1
            ),
            ContextItem(
                id="b", type="source", content={"y": 1}, priority=20, token_count=3
            ),
            ContextItem(
                id="c", type="insight", content={"z": 1}, priority=5, token_count=1
            ),
        ]
        builder.remove_duplicates()
        builder.prioritize()
        builder.truncate_to_fit(4)
        response = builder._format_response()
        assert response["total_tokens"] <= 4
        assert response["total_items"] >= 1
        assert "sources" in response and "notes" in response and "insights" in response

    @pytest.mark.asyncio
    async def test_convenience_builders(self):
        with patch(
            "open_notebook.utils.context_builder.ContextBuilder.build",
            new=AsyncMock(return_value={"ok": True}),
        ):
            result1 = await build_notebook_context("notebook:1")
            result2 = await build_source_context("source:1")
            result3 = await build_mixed_context(
                source_ids=["source:1"], note_ids=["note:1"], notebook_id="notebook:1"
            )

        assert result1["ok"] is True
        assert result2["ok"] is True
        assert result3["ok"] is True


class TestVersionUtilsAdditional:
    def test_get_version_from_github_poetry(self):
        response = MagicMock()
        response.text = "[tool.poetry]\nversion='1.2.3'\n"
        response.raise_for_status = MagicMock()
        with patch("requests.get", return_value=response):
            assert get_version_from_github("https://github.com/org/repo") == "1.2.3"

    def test_get_version_from_github_project_fallback(self):
        response = MagicMock()
        response.text = "[project]\nversion='2.0.0'\n"
        response.raise_for_status = MagicMock()
        with patch("requests.get", return_value=response):
            assert get_version_from_github("https://github.com/org/repo") == "2.0.0"

    def test_get_version_from_github_missing_version(self):
        response = MagicMock()
        response.text = "[project]\nname='x'\n"
        response.raise_for_status = MagicMock()
        with patch("requests.get", return_value=response):
            with pytest.raises(KeyError):
                get_version_from_github("https://github.com/org/repo")

    @pytest.mark.asyncio
    async def test_get_version_from_github_async_poetry(self):
        async_client = AsyncMock()
        async_client.get.return_value.text = "[tool.poetry]\nversion='3.4.5'\n"
        async_client.get.return_value.raise_for_status = MagicMock()
        async_client_cm = AsyncMock()
        async_client_cm.__aenter__.return_value = async_client
        async_client_cm.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=async_client_cm):
            version = await get_version_from_github_async("https://github.com/org/repo")
        assert version == "3.4.5"

    @pytest.mark.asyncio
    async def test_get_version_from_github_async_invalid(self):
        with pytest.raises(ValueError):
            await get_version_from_github_async("https://example.com/org/repo")


class TestGraphUtilsAdditional:
    @pytest.mark.asyncio
    async def test_get_session_message_count_success(self):
        graph = MagicMock()
        state = SimpleNamespace(values={"messages": [1, 2, 3]})
        with patch("asyncio.to_thread", new=AsyncMock(return_value=state)):
            assert await get_session_message_count(graph, "session-1") == 3

    @pytest.mark.asyncio
    async def test_get_session_message_count_missing_state(self):
        graph = MagicMock()
        state = SimpleNamespace(values={})
        with patch("asyncio.to_thread", new=AsyncMock(return_value=state)):
            assert await get_session_message_count(graph, "session-2") == 0

    @pytest.mark.asyncio
    async def test_get_session_message_count_error(self):
        graph = MagicMock()
        with patch("asyncio.to_thread", new=AsyncMock(side_effect=Exception("x"))):
            assert await get_session_message_count(graph, "session-3") == 0


class FakeLanguageModel:
    def __init__(self, name: str = "model"):
        self.name = name

    def to_langchain(self):
        return {"langchain_model": self.name}


class TestProvisionAdditional:
    @pytest.mark.asyncio
    async def test_provision_large_context(self):
        with (
            patch("open_notebook.ai.provision.token_count", return_value=200000),
            patch("open_notebook.ai.provision.LanguageModel", FakeLanguageModel),
            patch(
                "open_notebook.ai.provision.model_manager.get_default_model",
                new=AsyncMock(return_value=FakeLanguageModel("large")),
            ) as mock_get_default,
        ):
            from open_notebook.ai.provision import provision_langchain_model

            result = await provision_langchain_model("x", None, "chat")
            assert result["langchain_model"] == "large"
            mock_get_default.assert_awaited_once_with("large_context")

    @pytest.mark.asyncio
    async def test_provision_explicit_model_id(self):
        with (
            patch("open_notebook.ai.provision.token_count", return_value=10),
            patch("open_notebook.ai.provision.LanguageModel", FakeLanguageModel),
            patch(
                "open_notebook.ai.provision.model_manager.get_model",
                new=AsyncMock(return_value=FakeLanguageModel("explicit")),
            ) as mock_get_model,
        ):
            from open_notebook.ai.provision import provision_langchain_model

            result = await provision_langchain_model("x", "model:1", "chat")
            assert result["langchain_model"] == "explicit"
            mock_get_model.assert_awaited_once_with("model:1")

    @pytest.mark.asyncio
    async def test_provision_default_type(self):
        with (
            patch("open_notebook.ai.provision.token_count", return_value=10),
            patch("open_notebook.ai.provision.LanguageModel", FakeLanguageModel),
            patch(
                "open_notebook.ai.provision.model_manager.get_default_model",
                new=AsyncMock(return_value=FakeLanguageModel("default")),
            ) as mock_get_default,
        ):
            from open_notebook.ai.provision import provision_langchain_model

            result = await provision_langchain_model("x", None, "transformation")
            assert result["langchain_model"] == "default"
            mock_get_default.assert_awaited_once_with("transformation")

    @pytest.mark.asyncio
    async def test_provision_no_model_raises(self):
        with (
            patch("open_notebook.ai.provision.token_count", return_value=10),
            patch(
                "open_notebook.ai.provision.model_manager.get_default_model",
                new=AsyncMock(return_value=None),
            ),
        ):
            from open_notebook.ai.provision import provision_langchain_model

            with pytest.raises(ValueError, match="No model configured"):
                await provision_langchain_model("x", None, "chat")

    @pytest.mark.asyncio
    async def test_provision_model_type_mismatch_raises(self):
        with (
            patch("open_notebook.ai.provision.token_count", return_value=10),
            patch("open_notebook.ai.provision.LanguageModel", FakeLanguageModel),
            patch(
                "open_notebook.ai.provision.model_manager.get_default_model",
                new=AsyncMock(return_value=object()),
            ),
        ):
            from open_notebook.ai.provision import provision_langchain_model

            with pytest.raises(ValueError, match="not a LanguageModel"):
                await provision_langchain_model("x", None, "chat")
