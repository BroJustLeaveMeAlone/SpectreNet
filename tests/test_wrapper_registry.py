# tests/test_wrapper_registry.py
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.wrappers.base import ToolWrapper


def test_registry_discovers_a_custom_wrapper(tmp_path):
    # Drop a fake wrapper file into a temp custom dir
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "__init__.py").write_text("")
    (custom / "fake.py").write_text(
        "from spectrenet.wrappers.base import ToolWrapper\n"
        "class FakeWrapper(ToolWrapper):\n"
        "    tool_name = 'fake'\n"
        "    @property\n"
        "    def schema(self): return {'ok': bool}\n"
        "    def run(self, **kw): return {'ok': True}\n"
    )
    reg = WrapperRegistry(extra_dirs=[custom])
    reg.discover()
    assert "fake" in reg.names()
    w = reg.get("fake")
    assert w.run() == {"ok": True}


def test_registry_skips_non_wrapper_classes(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "__init__.py").write_text("")
    (custom / "junk.py").write_text("class NotAWrapper:\n    pass\n")
    reg = WrapperRegistry(extra_dirs=[custom])
    reg.discover()
    assert reg.names() == [] or "junk" not in reg.names()
