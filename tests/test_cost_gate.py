from app.cli import CLICallbacks, should_proceed
from app.pipeline.run_log import RunLog


def test_auto_yes_always_proceeds_regardless_of_cost():
    assert should_proceed(1000.0, max_cost=None, auto_yes=True) is True


def test_max_cost_rejects_above_cap_even_with_auto_yes():
    assert should_proceed(10.0, max_cost=5.0, auto_yes=True) is False


def test_max_cost_allows_at_or_below_cap():
    assert should_proceed(5.0, max_cost=5.0, auto_yes=True) is True


def test_prompts_and_accepts_yes_answer():
    assert should_proceed(1.0, max_cost=None, auto_yes=False, prompt_fn=lambda _: "y") is True
    assert should_proceed(1.0, max_cost=None, auto_yes=False, prompt_fn=lambda _: "yes") is True


def test_prompts_and_rejects_non_yes_answer():
    assert should_proceed(1.0, max_cost=None, auto_yes=False, prompt_fn=lambda _: "n") is False
    assert should_proceed(1.0, max_cost=None, auto_yes=False, prompt_fn=lambda _: "") is False


def make_estimate_dict(total: float) -> dict:
    return {
        "breakdown": {
            "llm": total, "tts": 0.0, "images": 0.0, "video": 0.0, "stock": 0.0, "vlm": 0.0
        },
        "notes": [],
    }


async def test_cli_callbacks_on_cost_estimate_stores_estimate_on_run_log(tmp_path):
    run_log = RunLog(tmp_path, topic="t", archetype="infographic")
    callbacks = CLICallbacks(run_log, auto_yes=True, max_cost=None)
    try:
        proceed = callbacks.on_cost_estimate(make_estimate_dict(1.5))
        assert proceed is True
        assert run_log.cost_estimate is not None
        assert run_log.cost_estimate["breakdown"]["llm"] == 1.5
    finally:
        callbacks.restore_signal_handler()


async def test_cli_callbacks_on_cost_estimate_rejects_above_max_cost(tmp_path):
    run_log = RunLog(tmp_path, topic="t", archetype="infographic")
    callbacks = CLICallbacks(run_log, auto_yes=True, max_cost=1.0)
    try:
        proceed = callbacks.on_cost_estimate(make_estimate_dict(5.0))
        assert proceed is False
    finally:
        callbacks.restore_signal_handler()
