import app.pipeline.stock_resolver as stock_resolver_module
from app.config.archetype import ArchetypeConfig
from app.pipeline.stock_resolver import resolve_stock
from app.schema.director import Motion, Scene, Transition, VisualType
from app.schema.providers import StockAsset, StockCandidate, Usage
from app.schema.visuals import ImagePromptResult, QueryReformulationResult, VerificationResult


def make_archetype() -> ArchetypeConfig:
    return ArchetypeConfig(key="test", scene_pacing="fast")


def make_scene(visual_type=VisualType.STOCK_IMAGE, prompt="a dog in a park") -> Scene:
    return Scene(
        visual_type=visual_type,
        visual_prompt=prompt,
        motion=Motion.STATIC,
        script_line="narration",
        transition=Transition.NONE,
    )


def make_candidate(id_: str, provider: str = "fake") -> StockCandidate:
    return StockCandidate(
        id=id_,
        provider=provider,
        url=f"https://example.com/{id_}.jpg",
        preview_url=f"https://example.com/{id_}-preview.jpg",
        width=1080,
        height=1920,
        attribution=f"by someone ({id_})",
    )


class FakeStockProvider:
    def __init__(self, name, image_results=None):
        self.name = name
        self._image_results = list(image_results or [])
        self.search_image_calls = []
        self.download_calls = []

    async def search_image(self, query):
        self.search_image_calls.append(query)
        if not self._image_results:
            return []
        item = self._image_results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def search_video(self, query):
        return []

    async def download(self, candidate, dest_path):
        self.download_calls.append(candidate.id)
        dest_path.write_bytes(b"fake-stock-bytes")
        return StockAsset(
            file_path=str(dest_path),
            width=candidate.width,
            height=candidate.height,
            duration=candidate.duration,
            attribution=candidate.attribution,
        )


class FakeVerifier:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def verify(self, image_bytes, visual_prompt, narration):
        self.calls.append((visual_prompt, narration))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def generate(self, *, system_prompt, user_message, schema):
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        return self._responses.pop(0), Usage(input_tokens=0, output_tokens=0)


class FakeImageProvider:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, style=None):
        self.calls.append(prompt)
        return b"fake-ai-png"


async def _patched_fetch(monkeypatch):
    async def fake_fetch(candidate):
        return b"fake-preview-bytes"

    monkeypatch.setattr(stock_resolver_module, "_fetch_preview_bytes", fake_fetch)


async def test_accepts_first_candidate_when_verified(tmp_path, monkeypatch):
    await _patched_fetch(monkeypatch)
    provider = FakeStockProvider("fake", image_results=[[make_candidate("c1")]])
    verifier = FakeVerifier(
        [VerificationResult(relevant=True, confidence=0.9, reason="matches well")]
    )
    llm = ScriptedLLM([ImagePromptResult(prompt="unused")])
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    assert result.status == "generated"
    assert result.method == "stock_verified"
    assert result.confidence == 0.9
    assert result.path is not None
    assert image.calls == []  # never fell back to AI


async def test_rejects_then_reformulates_then_accepts(tmp_path, monkeypatch):
    await _patched_fetch(monkeypatch)
    provider = FakeStockProvider(
        "fake",
        image_results=[[make_candidate("c1")], [make_candidate("c2")]],
    )
    verifier = FakeVerifier(
        [
            VerificationResult(relevant=False, confidence=0.2, reason="wrong subject"),
            VerificationResult(relevant=True, confidence=0.8, reason="matches"),
        ]
    )
    llm = ScriptedLLM([QueryReformulationResult(queries=["a park bench"])])
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    assert result.status == "generated"
    assert result.method == "stock_verified"
    assert provider.search_image_calls == ["a dog in a park", "a park bench"]


async def test_budget_exhausted_falls_back_to_ai_image_with_negative_examples(
    tmp_path, monkeypatch
):
    await _patched_fetch(monkeypatch)
    # every candidate across every attempt is rejected
    provider = FakeStockProvider(
        "fake",
        image_results=[
            [make_candidate("c1")],
            [make_candidate("c2")],
            [make_candidate("c3")],
            [make_candidate("c4")],
        ],
    )
    verifier = FakeVerifier(
        [
            VerificationResult(relevant=False, confidence=0.1, reason=f"rejected {i}")
            for i in range(4)
        ]
    )
    llm = ScriptedLLM(
        [
            QueryReformulationResult(queries=["alt query"]),
            ImagePromptResult(prompt="a rewritten ai prompt"),
        ]
    )
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    assert result.status == "fallback"
    assert "no stock_image candidate verified within budget" in result.fallback_reason
    assert len(image.calls) == 1
    # the image prompter's LLM call (the last one) should carry the
    # rejected candidates' reasons as negative examples
    prompter_message = llm.calls[-1]["user_message"]
    assert "Avoid:" in prompter_message
    assert "rejected 0" in prompter_message


async def test_provider_fallback_order_tries_next_provider_on_error(tmp_path, monkeypatch):
    await _patched_fetch(monkeypatch)
    failing_provider = FakeStockProvider("failing", image_results=[RuntimeError("API down")])
    working_provider = FakeStockProvider("working", image_results=[[make_candidate("c1")]])
    verifier = FakeVerifier([VerificationResult(relevant=True, confidence=0.9, reason="good")])
    llm = ScriptedLLM([])
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[failing_provider, working_provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    assert result.status == "generated"
    assert failing_provider.search_image_calls == ["a dog in a park"]
    assert working_provider.search_image_calls == ["a dog in a park"]
    assert any("error" in entry for entry in log)


async def test_verifier_error_accepts_candidate_unverified(tmp_path, monkeypatch):
    await _patched_fetch(monkeypatch)
    provider = FakeStockProvider("fake", image_results=[[make_candidate("c1")]])
    verifier = FakeVerifier([RuntimeError("vision model unavailable")])
    llm = ScriptedLLM([])
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    assert result.status == "generated"
    assert result.method == "stock_unverified"
    assert result.confidence == -1


async def test_download_failure_does_not_crash_and_falls_back(tmp_path, monkeypatch):
    await _patched_fetch(monkeypatch)

    class DownloadFailsProvider(FakeStockProvider):
        async def download(self, candidate, dest_path):
            raise RuntimeError("download failed")

    provider = DownloadFailsProvider("fake", image_results=[[make_candidate("c1")]])
    verifier = FakeVerifier([VerificationResult(relevant=True, confidence=0.9, reason="good")])
    llm = ScriptedLLM([QueryReformulationResult(queries=["anything"])])
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    # download failed on the only candidate, so it falls through to AI fallback
    assert result.status == "fallback"
    assert len(image.calls) == 1


async def test_attribution_is_carried_through_to_result(tmp_path, monkeypatch):
    await _patched_fetch(monkeypatch)
    provider = FakeStockProvider("fake", image_results=[[make_candidate("c1")]])
    verifier = FakeVerifier([VerificationResult(relevant=True, confidence=0.9, reason="good")])
    llm = ScriptedLLM([])
    image = FakeImageProvider()
    log: list[dict] = []

    result = await resolve_stock(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        stock_providers=[provider],
        verifier=verifier,
        llm=llm,
        image=image,
        assets_dir=tmp_path,
        log_attempts=log,
    )

    assert result.attribution == "by someone (c1)"
