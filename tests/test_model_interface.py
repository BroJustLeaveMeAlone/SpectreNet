# tests/test_model_interface.py
from spectrenet.model.interface import ModelInterface

class EchoModel(ModelInterface):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return f"[{system_prompt}] {user_prompt}"

def test_model_interface_single_method_contract():
    m = EchoModel()
    assert m.complete("sys", "hello") == "[sys] hello"

def test_model_interface_is_abstract():
    try:
        ModelInterface()
        assert False, "should be abstract"
    except TypeError:
        pass
