import ast

from scripts.pipeline_runner import LocalPipelineRunner


def runner():
    r = LocalPipelineRunner.__new__(LocalPipelineRunner)
    r.profile = {"language": "python", "default_ext": ".py"}
    return r


def class_methods(source, name):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == name)
    return [m.name for m in node.body if isinstance(m, ast.FunctionDef)]


def test_insert_goes_into_class_before_module_aliases():
    source = "class A:\n    def old(self):\n        return 1\n\n# Aliases\nB = A\n"
    patched, action = runner().upsert_method_into_content(source, "new", "def new(self):\n    return 2")
    assert action == "INSERTED"
    assert class_methods(patched, "A") == ["old", "new"]
    assert "# Aliases\nB = A" in patched


def test_insert_goes_into_last_class_before_main_guard():
    source = "class A:\n    x = 1\n\nclass C:\n    y = 2\n\nif __name__ == '__main__':\n    print(1)\n"
    patched, _ = runner().upsert_method_into_content(source, "new", "def new(self):\n    return 2")
    assert class_methods(patched, "C") == ["new"]
    assert patched.rstrip().endswith("print(1)")


def test_module_without_class_inserts_top_level_function():
    patched, _ = runner().upsert_method_into_content("X = 1\n", "new", "def new():\n    return 2")
    assert any(isinstance(n, ast.FunctionDef) and n.name == "new" for n in ast.parse(patched).body)
