import argparse
import re
import sys
import unittest
from typing import Any, Dict, List, Tuple, Optional

from lark import Lark, Transformer, v_args, Token
from lark.exceptions import UnexpectedInput


class ParseError(Exception):
    pass

NUMBER_RE = r"-?(?:\d+\.\d+|\d+\.(?!\s)|\.\d+|\d+)(?:[eE][+-]?\d+)?"


GRAMMAR = rf"""
start: global_decl* dict

global_decl: "global" NAME "=" value ";"?

dict: "begin" pair* "end"
pair: NAME ":=" value ";"

?value: NUMBER      -> number
      | STRING      -> string
      | array
      | dict
      | const_ref

# Массивы по варианту: { значение. значение. значение. ... }
array: "{{" [value ("." value)*] "}}"

const_ref: "!" "(" NAME ")"

# FIX: поддержка подчёркиваний в именах (tax_rate, default_port, hp_base, ...)
NAME: /[a-zA-Z][a-zA-Z0-9_]*/
NUMBER: /{NUMBER_RE}/
STRING: ESCAPED_STRING

%import common.ESCAPED_STRING
%import common.WS_INLINE
%import common.NEWLINE

%ignore WS_INLINE
%ignore NEWLINE

LINE_COMMENT: /\|\|[^\n]*/
%ignore LINE_COMMENT

BLOCK_COMMENT: /--\[\[[\s\S]*?\]\]/
%ignore BLOCK_COMMENT
"""

parser = Lark(GRAMMAR, start="start", parser="lalr")


@v_args(inline=True)
class Build(Transformer):
    def NAME(self, t: Token) -> str:
        return str(t)

    def number(self, t: Token) -> Any:
        s = str(t)
        if re.search(r"[.eE]", s):
            return float(s)
        return int(s)

    def string(self, t: Token) -> str:
        return bytes(str(t)[1:-1], "utf-8").decode("unicode_escape")

    def array(self, *items: Any) -> List[Any]:
        return list(items)

    def const_ref(self, name: str) -> Tuple[str, str]:
        return ("__REF__", name)

    def pair(self, k: str, v: Any) -> Tuple[str, Any]:
        return (k, v)

    def dict(self, *pairs: Tuple[str, Any]) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for k, v in pairs:
            d[k] = v
        return d

    def global_decl(self, name: str, value: Any) -> Tuple[str, Any]:
        return (name, value)

    def start(self, *items: Any) -> Tuple[List[Tuple[str, Any]], Dict[str, Any]]:
        globals_list: List[Tuple[str, Any]] = []
        body: Optional[Dict[str, Any]] = None

        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and isinstance(it[0], str):
                globals_list.append(it)
            elif isinstance(it, dict):
                body = it

        if body is None:
            raise ParseError("Ожидался корневой словарь: begin ... end")
        return globals_list, body


def resolve_refs(obj: Any, consts: Dict[str, Any]) -> Any:
    if isinstance(obj, tuple) and len(obj) == 2 and obj[0] == "__REF__":
        name = obj[1]
        if name not in consts:
            raise ParseError(f"Неизвестная константа {name!r}")
        return consts[name]

    if isinstance(obj, dict):
        return {k: resolve_refs(v, consts) for k, v in obj.items()}

    if isinstance(obj, list):
        return [resolve_refs(v, consts) for v in obj]

    return obj


# TOML emit

def escape_toml_string(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\t", "\\t")
    s = s.replace("\r", "\\r")
    s = s.replace("\n", "\\n")
    return s


def render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{escape_toml_string(value)}"'
    if isinstance(value, list):
        return "[ " + ", ".join(render_value(v) for v in value) + " ]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {render_value(v)}" for k, v in value.items()) + " }"
    raise ValueError(f"Неподдерживаемый тип значения для TOML: {type(value)}")


def emit_table(d: Dict[str, Any], lines: List[str], prefix: Optional[str] = None) -> None:
    for k, v in d.items():
        if isinstance(v, dict):
            continue
        lines.append(f"{k} = {render_value(v)}")

    for k, v in d.items():
        if not isinstance(v, dict):
            continue
        full = k if prefix is None else f"{prefix}.{k}"
        if prefix is not None or lines:
            lines.append("")
        lines.append(f"[{full}]")
        emit_table(v, lines, full)


def to_toml(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    emit_table(data, lines)
    return "\n".join(lines) + "\n"


def process_text(text: str) -> str:
    try:
        tree = parser.parse(text)
        globals_list, body = Build().transform(tree)

        consts: Dict[str, Any] = {}
        for name, raw_val in globals_list:
            consts[name] = resolve_refs(raw_val, consts)

        data = resolve_refs(body, consts)
        if not isinstance(data, dict):
            raise ParseError("Корневой конфигурацией должен быть словарь (begin ... end)")

        return to_toml(data)

    except UnexpectedInput as e:
        ctx = ""
        try:
            ctx = e.get_context(text, span=50).rstrip()
        except Exception:
            pass
        msg = f"Синтаксическая ошибка на {e.line}:{e.column}"
        if ctx:
            msg += "\n" + ctx
        raise ParseError(msg)


#Tests 

class TestVariant5(unittest.TestCase):
    def test_arrays_with_dots(self):
        src = """
        begin
            a := {1. 2. 3};
        end
        """
        toml = process_text(src)
        self.assertIn("a = [ 1, 2, 3 ]", toml)

    def test_comments(self):
        src = """
        || one-line
        --[[
        multi
        ]]
        begin
            x := 1;
        end
        """
        toml = process_text(src)
        self.assertEqual(toml.strip(), "x = 1")

    def test_globals_and_refs(self):
        src = """
        global p = 8080
        begin
            server := begin
                port := !(p);
            end;
        end
        """
        toml = process_text(src)
        self.assertIn("[server]", toml)
        self.assertIn("port = 8080", toml)

    def test_underscores_in_names(self):
        src = """
        global default_port = 8080
        begin
            server_cfg := begin
                port := !(default_port);
            end;
        end
        """
        toml = process_text(src)
        self.assertIn("[server_cfg]", toml)
        self.assertIn("port = 8080", toml)

    def test_extended_numbers(self):
        src = """
        begin
            a := -10;
            b := 3.14;
            c := 2.;
            d := .5;
            e := -1e3;
            f := -3.14e-2;
            g := -.5E+2;
        end
        """
        toml = process_text(src)
        self.assertIn("a = -10", toml)
        self.assertIn("b = 3.14", toml)
        self.assertIn("c = 2.0", toml)
        self.assertIn("d = 0.5", toml)
        self.assertIn("e = -1000.0", toml)
        self.assertIn("f = -0.0314", toml)
        self.assertIn("g = -50.0", toml)

    def test_string_escaping_toml(self):
        src = r"""
        begin
            path := "C:\\temp\\a.txt";
            quote := "He said: \"ok\"";
            nl := "line1\nline2";
        end
        """
        toml = process_text(src)
        self.assertIn(r'path = "C:\\\\temp\\\\a.txt"', toml)
        self.assertIn(r'quote = "He said: \"ok\""', toml)
        self.assertIn(r'nl = "line1\\nline2"', toml)


def run_tests() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestVariant5)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


# CLI

def main_cli(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Преобразователь учебного конфигурационного языка (вариант №5) в TOML"
    )
    ap.add_argument("--input", help="путь к входному .ucfg файлу")
    ap.add_argument("--test", action="store_true", help="запустить встроенные тесты")
    args = ap.parse_args(argv[1:])

    if args.test:
        return run_tests()

    if not args.input:
        print("Ошибка: не указан --input <file>", file=sys.stderr)
        return 2

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
        sys.stdout.write(process_text(text))
        return 0
    except FileNotFoundError:
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 1
    except ParseError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main_cli(sys.argv))
