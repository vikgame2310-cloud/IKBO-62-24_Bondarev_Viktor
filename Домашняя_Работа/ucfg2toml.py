from lark import Lark, Transformer, v_args, Token
import re


class ParseError(Exception):
    pass


GRAMMAR = r"""
start: global_decl* dict

global_decl: "global" NAME "=" value ";"?

dict: "begin" pair* "end"
pair: NAME ":=" value ";"

?value: NUMBER      -> number
      | STRING      -> string
      | array
      | dict
      | const_ref

array: "{" [value (sep value)*] "}"
sep: "," | _WS

const_ref: "!" "(" NAME ")"

NAME: /[a-zA-Z][a-zA-Z0-9]*/

NUMBER: /-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?/
STRING: ESCAPED_STRING

%import common.ESCAPED_STRING
%import common.WS_INLINE
%import common.NEWLINE

_WS: /[ \t\r\n]+/

%ignore WS_INLINE
%ignore NEWLINE

LINE_COMMENT: /\|\|[^\n]*/
%ignore LINE_COMMENT

BLOCK_COMMENT: /--\[\[[\s\S]*?\]\]/
%ignore BLOCK_COMMENT
"""

parser = Lark(GRAMMAR, start="start", parser="lalr")


@v_args(inline=True)
class BuildAST(Transformer):
    def NAME(self, t: Token):
        return str(t)

    def number(self, t: Token):
        s = str(t)
        if re.search(r"[.eE]", s):
            return float(s)
        return int(s)

    def string(self, t: Token):
        return bytes(str(t)[1:-1], "utf-8").decode("unicode_escape")

    def array(self, *items):
        return list(items)

    def const_ref(self, name):
        return ("__REF__", name)

    def pair(self, k, v):
        return (k, v)

    def dict(self, *pairs):
        d = {}
        for k, v in pairs:
            d[k] = v
        return d

    def global_decl(self, name, value):
        return (name, value)

    def start(self, *items):
        globals_list = []
        body = None
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and isinstance(it[0], str):
                globals_list.append(it)
            elif isinstance(it, dict):
                body = it
        return globals_list, body


def resolve_refs(obj, consts):
    if isinstance(obj, tuple) and obj[0] == "__REF__":
        name = obj[1]
        if name not in consts:
            raise ParseError(f"Неизвестная константа {name!r}")
        return consts[name]

    if isinstance(obj, dict):
        return {k: resolve_refs(v, consts) for k, v in obj.items()}

    if isinstance(obj, list):
        return [resolve_refs(v, consts) for v in obj]

    return obj


def render_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[ " + ", ".join(render_value(v) for v in value) + " ]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {render_value(v)}" for k, v in value.items()) + " }"
    raise ValueError(f"Неподдерживаемый тип значения: {type(value)}")


def emit_table(d, lines, prefix=None):
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


def to_toml(data):
    lines = []
    emit_table(data, lines)
    return "\n".join(lines) + "\n"


def process_text(text: str) -> str:
    try:
        tree = parser.parse(text)
        globals_list, body = BuildAST().transform(tree)

        consts = {}
        for name, raw_val in globals_list:
            consts[name] = resolve_refs(raw_val, consts)

        data = resolve_refs(body, consts)
        if not isinstance(data, dict):
            raise ParseError("Корневой конфигурацией должен быть словарь (begin ... end)")

        return to_toml(data)

    except Exception as e:
        if isinstance(e, ParseError):
            raise
        raise ParseError(str(e))
