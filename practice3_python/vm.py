import sys
import xml.etree.ElementTree as ET

# Опкоды из спецификации УВМ (вариант 5)
OP_LOAD_CONST = 30  # загрузка константы
OP_LOAD = 5         # чтение значения из памяти
OP_STORE = 33       # запись значения в память
OP_ROR = 37         # побитовый циклический сдвиг вправо (для этапа 4)

NUM_REGS = 8                # B и C по 3 бита => 8 регистров
DEFAULT_MEMORY_SIZE = 65536  # размер единой памяти УВМ (команды + данные)


def load_binary(path: str) -> list[int]:
    """Читает бинарный файл программы и возвращает список байт (ints 0..255)."""
    with open(path, "rb") as f:
        data = f.read()
    return list(data)


def decode_instruction(memory: list[int], pc: int, code_size: int):
    """
    Декодирование одной команды из объединённой памяти.
    Возвращает (A, B, C, size) или (None, None, None, 0), если команд больше нет.
    """
    # Любая команда занимает минимум 2 байта
    if pc + 2 > code_size:
        return None, None, None, 0

    byte0 = memory[pc]
    byte1 = memory[pc + 1]
    first_two = byte0 | (byte1 << 8)

    # A — 6 младших бит
    A = first_two & 0x3F

    # LOAD_CONST (4 байта), остальные — 2 байта
    if A == OP_LOAD_CONST:
        if pc + 4 > code_size:
            raise ValueError("Неполная команда LOAD_CONST в конце файла")

        byte2 = memory[pc + 2]
        byte3 = memory[pc + 3]

        # 4-байтовое слово, как в ассемблере
        word = byte0 | (byte1 << 8) | (byte2 << 16) | (byte3 << 24)

        A = word & 0x3F
        B = (word >> 6) & 0x07
        C = (word >> 9) & ((1 << 17) - 1)  # 17 бит
        size = 4
    else:
        # 2-байтовая команда
        word = first_two
        B = (word >> 6) & 0x07
        C = (word >> 9) & 0x07  # 3 бита
        size = 2

    return A, B, C, size


def execute_instruction(A: int, B: int, C: int,
                        registers: list[int],
                        memory: list[int]):
    """
    Выполнение одной команды по спецификации варианта 5.

    - LOAD_CONST (30):
        Операнд: поле C.
        Результат: регистр по адресу, которым является поле B.

    - LOAD (5):
        Операнд: значение в памяти по адресу,
                 которым является регистр по адресу, которым является поле C.
        Результат: регистр по адресу, которым является поле B.

    - STORE (33):
        Операнд: регистр по адресу, которым является поле B.
        Результат: значение в памяти по адресу,
                   которым является регистр по адресу, которым является поле C.

    - ROR (37) — реализован на будущее (этап 4), сейчас можно не использовать.
    """
    if A == OP_LOAD_CONST:
        # registers[B] := C
        registers[B] = C

    elif A == OP_LOAD:
        addr_reg = C                       # адрес регистра-адреса
        addr = registers[addr_reg]         # значение регистра = адрес в памяти
        if not (0 <= addr < len(memory)):
            raise IndexError(f"LOAD: выход за пределы памяти: addr={addr}")
        registers[B] = memory[addr]

    elif A == OP_STORE:
        src_reg = B
        addr_reg = C
        addr = registers[addr_reg]
        if not (0 <= addr < len(memory)):
            raise IndexError(f"STORE: выход за пределы памяти: addr={addr}")
        memory[addr] = registers[src_reg]

    elif A == OP_ROR:
        # побитовый циклический сдвиг вправо:
        # первый операнд: регистр B
        # второй операнд: значение в памяти по адресу, которым является
        #                 регистр по адресу C
        reg_index = B
        addr_reg = C
        addr = registers[addr_reg]
        if not (0 <= addr < len(memory)):
            raise IndexError(f"ROR: выход за пределы памяти: addr={addr}")
        shift = memory[addr]

        value = registers[reg_index]
        width = 32
        mask = (1 << width) - 1
        value &= mask
        shift %= width

        rotated = ((value >> shift) | (value << (width - shift))) & mask
        registers[reg_index] = rotated

    else:
        raise ValueError(f"Неизвестный opcode A={A}")


def run_program(program_bytes: list[int], memory_size: int = DEFAULT_MEMORY_SIZE):
    """
    Загружает программу в объединённую память, запускает интерпретатор
    и возвращает (registers, memory) после выполнения.
    """
    if len(program_bytes) > memory_size:
        raise ValueError("Программа не помещается в память УВМ")

    # Единая память: сначала байты программы, дальше — нули (данные)
    memory = [0] * memory_size
    for i, b in enumerate(program_bytes):
        memory[i] = b

    registers = [0] * NUM_REGS
    pc = 0
    code_size = len(program_bytes)

    # Основной цикл интерпретатора
    while pc < code_size:
        A, B, C, size = decode_instruction(memory, pc, code_size)
        if size == 0:
            break  # больше команд нет

        execute_instruction(A, B, C, registers, memory)
        pc += size

    return registers, memory


def dump_memory_to_xml(memory: list[int],
                       registers: list[int],
                       dump_path: str,
                       start_addr: int,
                       end_addr: int):
    """
    Сохраняет дамп памяти в XML:
    <uvm_dump>
      <memory start=".." end="..">
        <cell addr="i">value</cell>
        ...
      </memory>
      <registers>
        <reg index="k">value</reg>
        ...
      </registers>
    </uvm_dump>
    """
    if start_addr < 0 or end_addr >= len(memory):
        raise ValueError("Диапазон адресов выходит за пределы памяти")

    root = ET.Element("uvm_dump")

    mem_el = ET.SubElement(
        root,
        "memory",
        start=str(start_addr),
        end=str(end_addr)
    )

    for addr in range(start_addr, end_addr + 1):
        cell_el = ET.SubElement(mem_el, "cell", addr=str(addr))
        cell_el.text = str(memory[addr])

    regs_el = ET.SubElement(root, "registers")
    for i, value in enumerate(registers):
        reg_el = ET.SubElement(regs_el, "reg", index=str(i))
        reg_el.text = str(value)

    tree = ET.ElementTree(root)
    tree.write(dump_path, encoding="utf-8", xml_declaration=True)


def main():
    # Ожидаемые аргументы:
    # python vm.py program.bin dump.xml start_addr end_addr
    if len(sys.argv) != 5:
        print("Использование: python vm.py program.bin dump.xml start_addr end_addr")
        sys.exit(1)

    program_path = sys.argv[1]
    dump_path = sys.argv[2]

    try:
        start_addr = int(sys.argv[3])
        end_addr = int(sys.argv[4])
    except ValueError:
        print("start_addr и end_addr должны быть целыми числами")
        sys.exit(1)

    if start_addr < 0 or end_addr < start_addr:
        print("Некорректный диапазон адресов памяти")
        sys.exit(1)

    # 1) читаем бинарную программу
    program_bytes = load_binary(program_path)

    # 2) запускаем интерпретатор
    registers, memory = run_program(program_bytes, DEFAULT_MEMORY_SIZE)

    # 3) делаем дамп памяти в XML по указанному диапазону
    try:
        dump_memory_to_xml(memory, registers, dump_path, start_addr, end_addr)
    except ValueError as e:
        print("Ошибка при формировании дампа:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
