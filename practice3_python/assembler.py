import sys
import yaml


def load_program(path):

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "program" not in data:
        raise ValueError("В YAML должен быть объект с ключом 'program'")

    return data["program"]

def instr_to_fields(ins):

    op = ins["op"].upper()

    if op == "LOAD_CONST":
        A = 30
        B = int(ins["dst"])
        C = int(ins["value"])

    elif op == "LOAD":
        A = 5
        B = int(ins["dst"])
        C = int(ins["addr_reg"])

    elif op == "STORE":
        A = 33
        B = int(ins["src"])
        C = int(ins["addr_reg"])

    elif op == "ROR":
        A = 37
        B = int(ins["dst"])
        C = int(ins["mem_reg"])

    else:
        raise ValueError("Неизвестная операция:", op)

    return op, A, B, C

def encode_load_const(A: int, B: int, C: int) -> bytes:

    A_masked = A & 0x3F            # 6 бит: 0b11_1111
    B_masked = B & 0x07            # 3 бита: 0b111

    C_masked = C & ((1 << 17) - 1)

    word = A_masked | (B_masked << 6) | (C_masked << 9)

    # По заданию размер команды 4 байта
    return word.to_bytes(4, byteorder="little")

def encode_load(A: int, B: int, C: int) -> bytes:

    A_masked = A & 0x3F
    B_masked = B & 0x07
    C_masked = C & 0x07  # 3 бита

    word = A_masked | (B_masked << 6) | (C_masked << 9)
    return word.to_bytes(2, byteorder="little")

def encode_store(A: int, B: int, C: int) -> bytes:

    A_masked = A & 0x3F
    B_masked = B & 0x07
    C_masked = C & 0x07

    word = A_masked | (B_masked << 6) | (C_masked << 9)
    return word.to_bytes(2, byteorder="little")

def encode_ror(A: int, B: int, C: int) -> bytes:

    A_masked = A & 0x3F
    B_masked = B & 0x07
    C_masked = C & 0x07

    word = A_masked | (B_masked << 6) | (C_masked << 9)
    return word.to_bytes(2, byteorder="little")

def encode_instruction(op: str, A: int, B: int, C: int) -> bytes:

    if op == "LOAD_CONST":
        return encode_load_const(A, B, C)
    elif op == "LOAD":
        return encode_load(A, B, C)
    elif op == "STORE":
        return encode_store(A, B, C)
    elif op == "ROR":
        return encode_ror(A, B, C)
    else:
        raise ValueError("Неизвестная операция при кодировании:", op)


def main():
    if len(sys.argv) < 3:
        print("Использование: python assembler.py source.yaml out.bin [--test]")
        sys.exit(1)

    source = sys.argv[1]
    output = sys.argv[2]
    test_mode = "--test" in sys.argv

    program = load_program(source)

    abc_list = []
    all_bytes = bytearray()

    for ins in program:
        op, A, B, C = instr_to_fields(ins)
        abc_list.append((A, B, C))
        encoded = encode_instruction(op, A, B, C)
        all_bytes.extend(encoded)

    with open(output, "wb") as f:
        f.write(all_bytes)

    print(f"Размер бинарного файла: {len(all_bytes)} байт")

    if test_mode:
        print("Внутреннее представление (A, B, C):")
        for A, B, C in abc_list:
            print(f"A={A} B={B} C={C}")

        hex_bytes = ", ".join(f"0x{b:02X}" for b in all_bytes)
        print("Машинный код:")
        print(hex_bytes)


if __name__ == "__main__":
    main()
