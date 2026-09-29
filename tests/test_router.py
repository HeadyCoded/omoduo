"""Tests for TaskRouter intent and prefix routing."""

from omoduo.engine.router import TaskRouter

def test_explicit_prefixes():
    router = TaskRouter()

    dec_claude = router.route("@claude refactor the auth system")
    assert dec_claude.primary_engine == "claude"
    assert dec_claude.clean_prompt == "refactor the auth system"

    dec_agy = router.route("@agy search codebase for pipewire config")
    assert dec_agy.primary_engine == "agy"
    assert dec_agy.clean_prompt == "search codebase for pipewire config"

    dec_both = router.route("@both plan and review the sqlite schema")
    assert dec_both.primary_engine == "both"
    assert dec_both.clean_prompt == "plan and review the sqlite schema"

def test_agy_heuristics():
    router = TaskRouter()

    dec1 = router.route("find all files that import textual")
    assert dec1.primary_engine == "agy"

    dec2 = router.route("explain flow of the audio pipeline")
    assert dec2.primary_engine == "agy"

    dec3 = router.route("give me a codebase overview of golive")
    assert dec3.primary_engine == "agy"

def test_claude_heuristics():
    router = TaskRouter()

    dec1 = router.route("refactor the websocket handler")
    assert dec1.primary_engine == "claude"

    dec2 = router.route("fix this bug with the null check")
    assert dec2.primary_engine == "claude"

    dec3 = router.route("write a unit test for the date scrubber")
    assert dec3.primary_engine == "claude"

def test_dual_heuristics():
    router = TaskRouter()

    dec1 = router.route("can both of you collaborate on this architectural shift?")
    assert dec1.primary_engine == "both"

    dec2 = router.route("work together to make me an animation in ASCII code of a parrot")
    assert dec2.primary_engine == "both"

def test_conversational_stickiness():
    router = TaskRouter()

    # When prompt is a short follow up, stick with last active engine
    dec = router.route("can you help me do it?", last_engine="claude")
    assert dec.primary_engine == "claude"
    assert "Follow-up turn continuation" in dec.reason

def test_fallback_default():
    router = TaskRouter()

    dec = router.route("what time does the stream start?")
    assert dec.primary_engine == "claude"

def test_remote_prefix():
    router = TaskRouter()

    dec = router.route("@remote fix the off-by-one in the loop")
    assert dec.primary_engine == "remote"
    assert dec.clean_prompt == "fix the off-by-one in the loop"

    dec2 = router.route("@local add a docstring")
    assert dec2.primary_engine == "remote"
    assert dec2.clean_prompt == "add a docstring"

def test_all_prefix():
    router = TaskRouter()

    dec = router.route("@all what does this function do?")
    assert dec.primary_engine == "all"
    assert dec.clean_prompt == "what does this function do?"

    dec2 = router.route("@compare summarize the config module")
    assert dec2.primary_engine == "all"

def test_duo_prefix():
    router = TaskRouter()

    dec = router.route("@duo build the settings screen")
    assert dec.primary_engine == "duo"
    assert dec.clean_prompt == "build the settings screen"

def test_stickiness_includes_new_engines():
    router = TaskRouter()

    for engine in ("remote", "all", "duo"):
        dec = router.route("keep going", last_engine=engine)
        assert dec.primary_engine == engine
