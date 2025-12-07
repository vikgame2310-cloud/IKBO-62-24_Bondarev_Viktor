# test_assembler.py
from assembler import instr_to_fields, encode_instruction


def main():
    # Тесты из спецификации УВМ (вариант 5)
    tests = [
        {
            "name": "LOAD_CONST A=30 B=5 C=748",
            "ins": {"op": "LOAD_CONST", "dst": 5, "value": 748},
            "expected_abc": (30, 5, 748),
            "expected_bytes": [0x5E, 0xD9, 0x05, 0x00],
        },
        {
            "name": "LOAD A=5 B=6 C=0",
            "ins": {"op": "LOAD", "dst": 6, "addr_reg": 0},
            "expected_abc": (5, 6, 0),
            "expected_bytes": [0x85, 0x01],
        },
        {
            "name": "STORE A=33 B=1 C=7",
            "ins": {"op": "STORE", "src": 1, "addr_reg": 7},
            "expected_abc": (33, 1, 7),
            "expected_bytes": [0x61, 0x0E],
        },
        {
            "name": "ROR A=37 B=7 C=5",
            "ins": {"op": "ROR", "dst": 7, "mem_reg": 5},
            "expected_abc": (37, 7, 5),
            "expected_bytes": [0xE5, 0x0B],
        },
    ]

    all_ok = True

    for test in tests:
        name = test["name"]
        ins = test["ins"]
        expected_abc = test["expected_abc"]
        expected_bytes = test["expected_bytes"]

        # 1. Считаем A,B,C
        op, A, B, C = instr_to_fields(ins)
        got_abc = (A, B, C)

        # 2. Кодируем в байты
        encoded = encode_instruction(op, A, B, C)
        got_bytes = list(encoded)

        print(f"Тест: {name}")

        print(f"  A,B,C получены: {got_abc}")
        print(f"  A,B,C ожидаются: {expected_abc}")

        print(f"Тест (A={got_abc[0]}, B={got_abc[1]}, C={got_abc[2]}):")
        print("  Получено:  " + ", ".join(f"0x{b:02X}" for b in got_bytes))
        print("  Ожидается: " + ", ".join(f"0x{b:02X}" for b in expected_bytes))

        if got_abc == expected_abc and got_bytes == expected_bytes:
            print("  => OK\n")
        else:
            print("  => FAIL\n")
            all_ok = False

    if all_ok:
        print("ИТОГ: ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print("ИТОГ: ЕСТЬ ОШИБКИ В РЕАЛИЗАЦИИ")


if __name__ == "__main__":
    main()
