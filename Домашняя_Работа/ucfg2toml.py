#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инструмент командной строки для учебного конфигурационного языка (Вариант №5).

Запуск:
    python ucfg2toml.py input.ucfg      # обычный запуск
    python ucfg2toml.py --test          # запустить встроенные тесты
"""

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Any, List, Dict, Tuple

import unittest



#   Лексер


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.col})"


class ParseError(Exception):
    pass


def remove_comments(text: str) -> str:
    text = re.sub(r'--\[\[.*?\]\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\|\|.*', '', text)
    return text


TOKEN_SPEC = [
    ("NUMBER", r'-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?'),
    ("GLOBAL", r'global\b'),
    ("BEGIN", r'begin\b'),
    ("END", r'end\b'),
    ("ASSIGN", r':='),
    ("EQUAL", r'='),
    ("LBRACE", r'\{'),
    ("RBRACE", r'\}'),
    ("SEMI", r';'),
    ("COMMA", r','),
    ("LPAREN", r'\('),
    ("RPAREN", r'\)'),
    ("BANG", r'!'),
    ("STRING", r'"[^"\n]*"'),
    ("NAME", r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ("NEWLINE", r'\n'),
    ("SKIP", r'[ \t\r]+'),
    ("MISMATCH", r'.'),
]

MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC),
    re.UNICODE,
)


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    line = 1
    col = 1

    for mo in MASTER_RE.finditer(text):
        kind = mo.lastgroup
        value = mo.group()
        if kind == "NEWLINE":
            line += 1
            col = 1
            continue
        elif kind == "SKIP":
            col += len(value)
            continue
        elif kind == "MISMATCH":
            raise ParseError(f"Неожиданный символ {value!r} на {line}:{col}")
        tokens.append(Token(kind, value, line, col))
        col += len(value)
    tokens.append(Token("EOF", "", line, col))
    return tokens



#   AST


@dataclass
class NumberNode:
    text: str


@dataclass
class StringNode:
    text: str


@dataclass
class ArrayNode:
    values: List[Any]


@dataclass
class DictNode:
    items: List[Tuple[str, Any]]


@dataclass
class ConstRefNode:
    name: str


ValueNode = Any



#   Парсер


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos]

    def accept(self, ttype: str) -> Token | None:
        if self.current().type == ttype:
            tok = self.current()
            self.pos += 1
            return tok
        return None

    def expect(self, ttype: str) -> Token:
        tok = self.accept(ttype)
        if not tok:
            cur = self.current()
            raise ParseError(
                f"Ожидался токен {ttype}, а найдено {cur.type} ({cur.value!r}) "
                f"на {cur.line}:{cur.col}"
            )
        return tok

    def parse(self) -> Tuple[Dict[str, ValueNode], DictNode]:
        consts_ast: Dict[str, ValueNode] = {}
        while self.current().type == "GLOBAL":
            name, value = self.global_decl(consts_ast)
            consts_ast[name] = value

        body = self.dict_literal()
        self.expect("EOF")
        return consts_ast, body

    def global_decl(self, existing_consts: Dict[str, ValueNode]) -> Tuple[str, ValueNode]:
        self.expect("GLOBAL")
        name_tok = self.expect("NAME")
        self.expect("EQUAL")
        value_node = self.value()
        self.accept("SEMI")

        eval_env: Dict[str, Any] = {}
        for cname, cnode in existing_consts.items():
            eval_env[cname] = eval_node(cnode, eval_env)

        const_value = eval_node(value_node, eval_env)
        return name_tok.value, python_to_ast(const_value)

    def dict_literal(self) -> DictNode:
        self.expect("BEGIN")
        items: List[Tuple[str, ValueNode]] = []
        while self.current().type != "END":
            if self.current().type == "EOF":
                cur = self.current()
                raise ParseError(
                    f"Ожидался 'end', но вход закончился (строка {cur.line})"
                )
            key_tok = self.expect("NAME")
            self.expect("ASSIGN")
            val = self.value()
            self.expect("SEMI")
            items.append((key_tok.value, val))
        self.expect("END")
        return DictNode(items)

    def array_literal(self) -> ArrayNode:
        self.expect("LBRACE")
        values: List[ValueNode] = []
        if self.current().type != "RBRACE":
            values.append(self.value())
            while self.accept("COMMA"):
                values.append(self.value())
        self.expect("RBRACE")
        return ArrayNode(values)

    def value(self) -> ValueNode:
        tok = self.current()
        if tok.type == "NUMBER":
            self.pos += 1
            return NumberNode(tok.value)
        elif tok.type == "STRING":
            self.pos += 1
            inner = tok.value[1:-1]
            return StringNode(inner)
        elif tok.type == "BEGIN":
            return self.dict_literal()
        elif tok.type == "LBRACE":
            return self.array_literal()
        elif tok.type == "BANG":
            self.expect("BANG")
            self.expect("LPAREN")
            name_tok = self.expect("NAME")
            self.expect("RPAREN")
            return ConstRefNode(name_tok.value)
        else:
            raise ParseError(
                f"Ожидалось значение, а найдено {tok.type} ({tok.value!r}) "
                f"на {tok.line}:{tok.col}"
            )



#   Вычисление AST


def parse_number(text: str) -> Any:
    t = text.replace(',', '.')
    if re.search(r'[.eE]', t):
        return float(t)
    else:
        return int(t)


def eval_node(node: ValueNode, consts: Dict[str, Any]) -> Any:
    if isinstance(node, NumberNode):
        return parse_number(node.text)
    elif isinstance(node, StringNode):
        return node.text
    elif isinstance(node, ArrayNode):
        return [eval_node(v, consts) for v in node.values]
    elif isinstance(node, DictNode):
        d: Dict[str, Any] = {}
        for k, v in node.items:
            d[k] = eval_node(v, consts)
        return d
    elif isinstance(node, ConstRefNode):
        if node.name not in consts:
            raise ParseError(f"Неизвестная константа {node.name!r}")
        return consts[node.name]
    else:
        return node


def python_to_ast(value: Any) -> ValueNode:
    if isinstance(value, (int, float)):
        return NumberNode(str(value))
    elif isinstance(value, str):
        return StringNode(value)
    elif isinstance(value, list):
        return ArrayNode([python_to_ast(v) for v in value])
    elif isinstance(value, dict):
        return DictNode([(k, python_to_ast(v)) for k, v in value.items()])
    else:
        raise ValueError(f"Неподдерживаемый тип для константы: {type(value)}")



#   Генератор TOML


def render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        elems = ", ".join(render_value(v) for v in value)
        return f"[ {elems} ]"
    if isinstance(value, dict):
        parts = [f"{k} = {render_value(v)}" for k, v in value.items()]
        return "{ " + ", ".join(parts) + " }"
    raise ValueError(f"Неподдерживаемый тип значения для TOML: {type(value)}")


def emit_table(
    d: Dict[str, Any],
    lines: List[str],
    prefix: str | None = None,
) -> None:
    for key, val in d.items():
        if isinstance(val, dict):
            continue
        lines.append(f"{key} = {render_value(val)}")

    for key, val in d.items():
        if not isinstance(val, dict):
            continue
        full_name = key if prefix is None else f"{prefix}.{key}"
        if prefix is not None or lines:
            lines.append("")
        lines.append(f"[{full_name}]")
        emit_table(val, lines, full_name)


def to_toml(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    emit_table(data, lines, prefix=None)
    return "\n".join(lines) + "\n"



#   CLI


def process_text(text: str) -> str:
    no_comments = remove_comments(text)
    tokens = tokenize(no_comments)
    parser = Parser(tokens)
    consts_ast, body_ast = parser.parse()

    consts: Dict[str, Any] = {}
    for name, node in consts_ast.items():
        consts[name] = eval_node(node, consts)

    data = eval_node(body_ast, consts)
    if not isinstance(data, dict):
        raise ParseError("Корневой конфигурацией должен быть словарь (begin ... end)")
    return to_toml(data)


def main_cli(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--test":
        unittest.main(argv=[argv[0]])
        return 0

    ap = argparse.ArgumentParser(
        description="Преобразователь учебного конфигурационного языка в TOML"
    )
    ap.add_argument("input", help="путь к входному файлу")
    args = ap.parse_args(argv[1:])

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
        toml = process_text(text)
        sys.stdout.write(toml)
        return 0
    except ParseError as e:
        print(f"Синтаксическая ошибка: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 1



#   Тесты


class TestConfigCompiler(unittest.TestCase):
    def test_deep_nesting(self):
        src = """
        begin
            world := begin
                regions := {
                    begin
                        name := "North";
                        temps := { -10, -5, 0 };
                    end,
                    begin
                        name := "South";
                        temps := { 20, 25, 30 };
                    end
                };
                meta := begin
                    version := 1;
                    flags := {1, 2, {3, 4}};
                end;
            end;
        end
        """
        toml = process_text(src)
        self.assertIn('name = "North"', toml)
        self.assertIn('name = "South"', toml)
        self.assertIn("version = 1", toml)

    def test_number_and_array(self):
        src = """
        begin
            x := 10;
            y := { 1, 2, 3 };
        end
        """
        toml = process_text(src)
        self.assertIn("x = 10", toml)
        self.assertIn("y = [ 1, 2, 3 ]", toml)

    def test_const_and_nested_dict(self):
        src = """
        global port = 8080
        global arr = {1,2,3}

        begin
            timeout := 30;
            server := begin
                p := !(port);
                nums := !(arr);
            end;
        end
        """
        toml = process_text(src)
        self.assertIn("timeout = 30", toml)
        self.assertIn("[server]", toml)
        self.assertIn("p = 8080", toml)
        self.assertIn("nums = [ 1, 2, 3 ]", toml)

    def test_comments(self):
        src = """
        || однострочный комментарий
        --[[
            многострочный
            комментарий
        ]]
        begin
            a := 1;
        end
        """
        toml = process_text(src)
        self.assertEqual(toml.strip(), "a = 1")

    def test_error_unknown_const(self):
        src = """
        begin
            x := !(NOT_DEFINED);
        end
        """
        with self.assertRaises(ParseError):
            process_text(src)

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

    def test_strings_basic(self):
        src = """
        begin
            name := "localhost";
            item := "sword";
        end
        """
        toml = process_text(src)
        self.assertIn('name = "localhost"', toml)
        self.assertIn('item = "sword"', toml)

    def test_strings_in_array_and_nested(self):
        src = """
        begin
            items := { "sword", "shield", "potion" };
            player := begin
                name := "Hero";
                class := "Warrior";
            end;
        end
        """
        toml = process_text(src)
        self.assertIn('items = [ "sword", "shield", "potion" ]', toml)
        self.assertIn("[player]", toml)
        self.assertIn('name = "Hero"', toml)
        self.assertIn('class = "Warrior"', toml)

    def test_string_const(self):
        src = """
        global host = "localhost"

        begin
            server := begin
                hostname := !(host);
            end;
        end
        """
        toml = process_text(src)
        self.assertIn("[server]", toml)
        self.assertIn('hostname = "localhost"', toml)



#   Примеры конфигураций


EXAMPLE_SERVER = """
global default_port = 8080
global default_host = "localhost"

begin
    server := begin
        host := !(default_host);
        port := !(default_port);
        max_clients := 100;
    end;
end
"""

EXAMPLE_GAME = """
global base_hp = 100
global base_damage = 12

begin
    player := begin
        name := "Hero";
        class := "Warrior";
        hp := !(base_hp);
        damage := !(base_damage);
        stats := begin
            strength := 15;
            agility := 10;
        end;
        inventory := { "sword", "shield", "potion" };
    end;
end
"""

EXAMPLE_FINANCE = """
global tax_rate = 0.13

begin
    salary := begin
        employee := "John Doe";
        gross := 100000;
        tax := !(tax_rate);
        months := {1,2,3,4,5,6,7,8,9,10,11,12};
    end;
end
"""


if __name__ == "__main__":
    raise SystemExit(main_cli(sys.argv))
