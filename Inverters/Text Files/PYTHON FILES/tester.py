import re
log_text = '''
I (332) MODBUS: Sent Request:
I (332) MODBUS: 0x3ffb8910   01 03 00 00 00 7b 05 e9                           |.....{..|
I (342) main_task: Returned from app_main()
I (1632) MODBUS: Received 251 bytes
I (1632) MODBUS: 0x3ffb71ec   01 03 f6 00 05 00 01 01  00 32 31 30 35 31 38 34  |.........2105184|
I (1632) MODBUS: 0x3ffb71fc   30 33 37 00 00 00 00 00  00 18 07 00 00 00 00 20  |037............ |
I (1642) MODBUS: 0x3ffb720c   03 10 57 00 00 10 01 40  10 00 00 86 a0 00 01 02  |..W....@........|
I (1652) MODBUS: 0x3ffb721c   03 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (1662) MODBUS: 0x3ffb722c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (1672) MODBUS: 0x3ffb723c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (1682) MODBUS: 0x3ffb724c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (1692) MODBUS: 0x3ffb725c   00 00 00 00 00 00 00 00  00 00 00 00 ff ff ff 19  |................|
I (1702) MODBUS: 0x3ffb726c   08 12 0f 06 19 ff ff ff  ff ff ff ff ff ff ff ff  |................|
I (1712) MODBUS: 0x3ffb727c   ff ff ff ff ff ff ff 00  01 ff ff 00 01 ff ff ff  |................|
I (1712) MODBUS: 0x3ffb728c   ff ff ff 00 01 00 00 ff  ff ff ff ff ff ff ff ff  |................|
I (1722) MODBUS: 0x3ffb729c   ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
I (1732) MODBUS: 0x3ffb72ac   ff ff ff ff ff 00 00 00  00 15 e0 15 e0 15 7c 00  |..............|.|
I (1742) MODBUS: 0x3ffb72bc   c8 11 94 00 14 00 5a 00  00 00 05 00 14 00 c8 ff  |......Z.........|
I (1752) MODBUS: 0x3ffb72cc   ff 00 00 00 01 00 19 03  de 00 0a 00 32 00 23 10  |............2.#.|
I (1762) MODBUS: 0x3ffb72dc   68 12 c0 11 30 00 f0 00  00 dc 53                 |h...0.....S|
I (1772) MODBUS: CRC valid.
I (2342) MODBUS: Sent Request:
I (2342) MODBUS: 0x3ffb8910   01 03 00 7b 00 7b 75 f0                           |...{.{u.|
I (3642) MODBUS: Received 251 bytes
I (3642) MODBUS: 0x3ffb71ec   01 03 f6 13 24 00 1e 00  28 13 24 00 1e 00 1e 00  |....$...(.$.....|
I (3642) MODBUS: 0x3ffb71fc   00 00 01 15 7c 00 00 00  00 13 ec 00 5f 15 18 00  |....|......._...|
I (3652) MODBUS: 0x3ffb720c   64 00 00 01 f4 00 03 00  01 00 01 27 10 00 0b 00  |d..........'....|
I (3662) MODBUS: 0x3ffb721c   00 00 ff 00 00 00 64 01  f4 03 84 05 14 06 a4 08  |......d.........|
I (3672) MODBUS: 0x3ffb722c   34 27 10 27 10 27 10 27  10 27 10 27 10 13 24 13  |4'.'.'.'.'.'..$.|
I (3682) MODBUS: 0x3ffb723c   24 13 24 13 24 13 24 13  24 00 50 00 50 00 50 00  |$.$.$.$.$.P.P.P.|
I (3692) MODBUS: 0x3ffb724c   50 00 50 00 50 00 01 00  01 00 01 00 01 00 01 00  |P.P.P...........|
I (3702) MODBUS: 0x3ffb725c   01 00 a2 ff ff 00 05 00  00 00 00 00 00 00 01 0a  |................|
I (3712) MODBUS: 0x3ffb726c   5a 07 3a 14 1e 12 8e 00  01 1f 40 1f 40 00 64 03  |Z.:.......@.@.d.|
I (3712) MODBUS: 0x3ffb727c   e8 00 00 00 00 75 30 00  00 af c8 00 00 01 90 00  |.....u0.........|
I (3722) MODBUS: 0x3ffb728c   00 00 32 00 00 01 86 00  00 00 37 00 03 a2 0e 00  |..2.......7.....|
I (3732) MODBUS: 0x3ffb729c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (3742) MODBUS: 0x3ffb72ac   00 00 00 00 00 00 00 00  00 00 00 ff ff ff ff ff  |................|
I (3752) MODBUS: 0x3ffb72bc   ff ff ff ff ff 0e ef ff  ff ff ff ff ff ff ff ff  |................|
I (3762) MODBUS: 0x3ffb72cc   ff ff ff ff ff ff ff 00  00 00 64 ff ff 00 00 ff  |..........d.....|
I (3772) MODBUS: 0x3ffb72dc   ff ff ff ff ff ff ff ff  ff a8 12                 |...........|
I (3782) MODBUS: CRC valid.
I (4342) MODBUS: Sent Request:
I (4342) MODBUS: 0x3ffb8910   01 03 00 f6 00 7b e5 db                           |.....{..|
I (5642) MODBUS: Received 251 bytes
I (5642) MODBUS: 0x3ffb71ec   01 03 f6 ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
I (5642) MODBUS: 0x3ffb71fc   ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
I (5652) MODBUS: 0x3ffb720c   ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff 03  |................|
I (5662) MODBUS: 0x3ffb721c   e8 03 e8 03 e8 03 e8 03  e8 03 e8 03 e8 03 e8 03  |................|
I (5672) MODBUS: 0x3ffb722c   e8 03 e8 03 e8 03 e8 03  e8 03 e8 03 e8 03 e8 03  |................|
I (5682) MODBUS: 0x3ffb723c   e8 03 e8 03 e8 03 e8 03  e8 03 e5 03 e8 03 e8 03  |................|
I (5692) MODBUS: 0x3ffb724c   e8 03 e8 03 e8 03 e8 03  e8 03 e8 03 e8 03 e8 ff  |................|
I (5702) MODBUS: 0x3ffb725c   ff 03 e8 03 e8 03 e8 03  e8 03 e8 03 e8 03 e8 03  |................|
I (5712) MODBUS: 0x3ffb726c   e8 03 e8 00 00 03 84 04  4c 05 14 05 dc 06 a4 07  |........L.......|
I (5712) MODBUS: 0x3ffb727c   6c 08 34 08 fc 09 c4 0a  8c 0b 54 0c 1c 00 00...(truncated 3078 characters)..........=M...P.|
I (9682) MODBUS: 0x3ffb723c   00 00 00 00 00 00 00 03  69 00 00 00 00 00 00 00  |........i.......|
I (9692) MODBUS: 0x3ffb724c   00 00 00 04 e2 05 d6 00  00 00 00 00 00 00 00 00  |................|
I (9702) MODBUS: 0x3ffb725c   00 00 00 00 00 00 00 08  00 00 01 00 05 00 00 00  |................|
I (9712) MODBUS: 0x3ffb726c   00 00 00 00 00 00 00 00  00 00 05 00 00 00 68 07  |..............h.|
I (9712) MODBUS: 0x3ffb727c   d0 07 d0 00 01 00 01 00  01 00 fa 00 05 00 02 00  |................|
I (9722) MODBUS: 0x3ffb728c   00 00 00 31 e6 00 2c 08  00 15 fe 00 00 00 00 00  |...1..,.........|
I (9732) MODBUS: 0x3ffb729c   00 01 5c 02 f8 01 7c 02  8a 00 02 00 00 00 00 04  |..\...|.........|
I (9742) MODBUS: 0x3ffb72ac   e2 14 b0 00 05 00 00 fc  0e f8 8c 00 d0 00 00 00  |................|
I (9752) MODBUS: 0x3ffb72bc   00 00 00 00 00 00 00 09  1b 09 23 09 25 00 00 00  |..........#.%...|
I (9762) MODBUS: 0x3ffb72cc   00 00 00 00 0b 00 0a ff  ff 00 14 00 00 13 7a 01  |..............z.|
I (9772) MODBUS: 0x3ffb72dc   07 00 f4 02 37 00 08 00  08 68 04                 |....7....h.|
I (9782) MODBUS: CRC valid.
I (10342) MODBUS: Sent Request:
I (10342) MODBUS: 0x3ffb8910   01 03 02 67 00 7b b5 8e                           |...g.{..|
I (11642) MODBUS: Received 251 bytes
I (11642) MODBUS: 0x3ffb71ec   01 03 f6 00 06 00 03 00  04 00 01 00 08 00 00 00  |................|
I (11642) MODBUS: 0x3ffb71fc   00 00 03 00 01 00 01 00  05 00 00 09 15 09 31 09  |..............1.|
I (11652) MODBUS: 0x3ffb720c   21 00 8c 00 8c 02 26 01  3d 01 55 05 3c 07 ce 00  |!.....&.=.U.<...|
I (11662) MODBUS: 0x3ffb721c   00 13 7a 00 00 01 45 01  5b 05 3d 07 dd 08 ff 09  |..z...E.[.=.....|
I (11672) MODBUS: 0x3ffb722c   25 09 1a 00 00 00 00 00  00 01 45 01 5b 05 3d 07  |%.........E.[.=.|
I (11682) MODBUS: 0x3ffb723c   dd 07 dd 13 7a 00 00 00  00 00 00 00 00 00 00 00  |....z...........|
I (11692) MODBUS: 0x3ffb724c   04 00 08 00 06 00 00 00  00 00 00 00 00 00 07 00  |................|
I (11702) MODBUS: 0x3ffb725c   1b 00 16 00 00 06 4a 05  bd 00 00 00 00 10 f3 00  |......J.........|
I (11712) MODBUS: 0x3ffb726c   25 0e df 00 27 00 00 00  00 00 00 00 00 00 00 00  |%...'...........|
I (11722) MODBUS: 0x3ffb727c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (11732) MODBUS: 0x3ffb728c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 ff ff  |................|
I (11742) MODBUS: 0x3ffb729c   ff 19 08 12 0f 06 23 ff  ff ff ff ff ff ff ff ff  |......#.........|
I (11752) MODBUS: 0x3ffb72ac   ff ff ff ff ff ff ff ff  ff 00 01 ff ff 00 01 ff  |................|
I (11752) MODBUS: 0x3ffb72bc   ff ff ff ff ff 00 01 00  00 ff ff ff ff ff ff ff  |................|
I (11762) MODBUS: 0x3ffb72cc   ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
I (11772) MODBUS: 0x3ffb72dc   ff ff ff ff ff ff ff 00  00 68 07                 |.........h.|
I (11782) MODBUS: CRC valid.
I (12342) MODBUS: Sent Request:
I (12342) MODBUS: 0x3ffb8910   01 03 02 e2 00 7b a4 67                           |.....{.g|
I (13642) MODBUS: Received 251 bytes
I (13642) MODBUS: 0x3ffb71ec   01 03 f6 00 00 15 e0 15  e0 00 00 00 00 00 00 00  |................|
I (13642) MODBUS: 0x3ffb71fc   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13652) MODBUS: 0x3ffb720c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13662) MODBUS: 0x3ffb721c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13672) MODBUS: 0x3ffb722c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13682) MODBUS: 0x3ffb723c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13692) MODBUS: 0x3ffb724c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13702) MODBUS: 0x3ffb725c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13712) MODBUS: 0x3ffb726c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13722) MODBUS: 0x3ffb727c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13732) MODBUS: 0x3ffb728c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13742) MODBUS: 0x3ffb729c   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13752) MODBUS: 0x3ffb72ac   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13752) MODBUS: 0x3ffb72bc   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13762) MODBUS: 0x3ffb72cc   00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
I (13772) MODBUS: 0x3ffb72dc   00 00 00 00 00 00 00 00  00 58 99                 |.........X.| 
I (13782) MODBUS: CRC valid.
'''

# Improved regex for start addresses, capturing function code 03
requests = re.findall(r'01 03 ([0-9a-f]{2} [0-9a-f]{2}) ([0-9a-f]{2} [0-9a-f]{2})', log_text, re.I)
start_addrs = []
request_lengths = []
for req, len_hex in requests:
    start_hex = req.replace(' ', '')
    len_hex = len_hex.replace(' ', '')
    try:
        start_int = int(start_hex, 16)
        length_int = int(len_hex, 16)
        start_addrs.append(start_int)
        request_lengths.append(length_int)
    except ValueError:
        print(f"Warning: Invalid hex in request: {req} {len_hex}")
        continue

# Extract data blocks
data_blocks = []
current_block = ''
lines = log_text.split('\n')
receiving = False
for line in lines:
    if 'Received' in line and 'bytes' in line:
        receiving = True
        current_block = ''
        continue
    if receiving and ('Sent Request:' in line or 'CRC valid' in line):
        receiving = False
        if current_block:
            data_blocks.append(current_block)
        continue
    if receiving and 'MODBUS: 0x' in line:
        hex_match = re.search(r'   ([0-9a-f ]+)   ', line)
        if hex_match:
            current_block += hex_match.group(1).replace(' ', '')

if receiving and current_block:
    data_blocks.append(current_block)

# Process registers
registers = {}
for idx, block in enumerate(data_blocks):
    if idx >= len(start_addrs):
        print(f"Warning: Data block {idx} has no corresponding request")
        continue
    if len(block) < 6:
        print(f"Warning: Data block {idx} too short: {len(block)} hex chars")
        continue
    try:
        byte_count = int(block[4:6], 16)
        expected_hex_len = 6 + byte_count * 2  # Header (3 bytes) + data
        if len(block) != expected_hex_len:
            print(f"Warning: Data block {idx} length mismatch: expected {expected_hex_len}, got {len(block)}")
            continue
        data_hex = block[6:]
        start_reg = start_addrs[idx]
        for i in range(0, len(data_hex), 4):
            word_hex = data_hex[i:i+4]
            if len(word_hex) != 4:
                print(f"Warning: Incomplete word in block {idx} at position {i}")
                continue
            try:
                value = int(word_hex, 16)
                reg_addr = start_reg + (i // 4)
                registers[reg_addr] = value
            except ValueError:
                print(f"Warning: Invalid hex word in block {idx}: {word_hex}")
                continue
    except ValueError:
        print(f"Warning: Invalid byte count in block {idx}: {block[:6]}")
        continue

# Targets (unchanged)
targets = {
    'Grid BUY Power 13W': 13, 'Grid Freq 49.8Hz': 498, 'Grid BUY Today 1.42kWh': 142,
    'Grid L1 232V': 2320, 'Grid L2 239V': 2390, 'Grid L3 233V': 2330,
    'Battery U 53.02V': 5302, 'Battery I -20.53A': -2053, 'Battery Power -1088W': -1088,
    'Battery Temp 25.0C': 250, 'Load Power 2080W': 2080, 'Load Today 22.2kWh': 2220,
    'Load L1 229V': 2290, 'Load L2 233V': 2330, 'Load L3 231V': 2310,
    'Solar Power 3095W': 3095, 'Solar Today 8.5kWh': 850, 'Solar PV1-V 434V': 4340,
    'Solar PV2-V 381V': 3810, 'Solar PV1-I 3.6A': 36, 'Solar PV2-I 3.8A': 38,
    'Solar PV1-P 1618W': 1618, 'Solar PV2-P 1477W': 1477
}

def to_signed(val):
    if val > 32767:
        return val - 65536
    return val

tolerance = 200
matches = {}
for label, target in targets.items():
    for reg, val in registers.items():
        signed_val = to_signed(val)
        if abs(val - target) <= tolerance or abs(signed_val - target) <= tolerance:
            if label not in matches:
                matches[label] = []
            matches[label].append((hex(reg), val, signed_val))

# Print matches
for label, match_list in matches.items():
    print(f"{label}:")
    for m in match_list:
        print(f"  Reg {m[0]}: {m[1]} (signed {m[2]})")