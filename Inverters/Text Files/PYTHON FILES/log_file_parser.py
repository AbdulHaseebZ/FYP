import re

# Path to the log file (update as needed)
log_file_path = "D:\\FYP\\PYTHON FILES\\log_file_inverex.txt"
output_file_path = "D:\\FYP\\PYTHON FILES\\modbus_registers.txt"

# Initialize a 16-bit array for registers 0x0000 to 0xFFFF (2^16 = 65536)
registers = [0xFFFF] * 65536  # Covers all possible Modbus register addresses

def parse_hex_data(hex_string):
    """Convert a space-separated hex string into a list of bytes."""
    hex_string = hex_string.replace(" ", "")
    return [int(hex_string[i:i+2], 16) for i in range(0, len(hex_string), 2)]

def bytes_to_16bit_values(byte_list):
    """Convert a list of bytes into a list of 16-bit values (big-endian)."""
    return [(byte_list[i] << 8) | byte_list[i+1] for i in range(0, len(byte_list), 2)]

# Read and parse the log file
current_start_address = None
num_registers = 0
data_lines = []
with open(log_file_path, 'r') as file:
    for line in file:
        # Look for a sent request to get the starting address and register count
        if "MODBUS: Sent Request:" in line:
            # Extract the hex data from the next line
            next_line = file.readline().strip()
            match = re.search(r'0x[0-9a-fA-F]+\s+((?:[0-9a-fA-F]{2}\s*)+)', next_line)
            if match:
                request_bytes = parse_hex_data(match.group(1))
                if len(request_bytes) >= 6:  # Ensure enough bytes for address and count
                    current_start_address = (request_bytes[2] << 8) | request_bytes[3]
                    num_registers = (request_bytes[4] << 8) | request_bytes[5]
                    data_lines = []  # Reset data lines for the new response
                else:
                    print(f"Warning: Invalid request format in line: {next_line}")
                    current_start_address = None
        # Look for received data
        elif "MODBUS: Received" in line and current_start_address is not None:
            # Extract the number of bytes received
            match = re.search(r'Received (\d+) bytes', line)
            if match:
                expected_bytes = 5 + 2 * num_registers  # 3 header + 2*num_registers + 2 CRC
                if int(match.group(1)) != expected_bytes:
                    print(f"Warning: Expected {expected_bytes} bytes, received {match.group(1)} at address {current_start_address:04x}")
                data_lines = []
        elif "MODBUS: 0x" in line and current_start_address is not None:
            # Extract hex data from the line
            match = re.search(r'0x[0-9a-fA-F]+\s+((?:[0-9a-fA-F]{2}\s*)+)', line)
            if match:
                data_lines.append(match.group(1))
        # Process the response when CRC is valid
        elif "MODBUS: CRC valid" in line and current_start_address is not None and data_lines:
            # Combine all data lines and parse hex bytes
            hex_data = " ".join(data_lines)
            byte_list = parse_hex_data(hex_data)
            # Verify response format: Slave ID (0x01), Function Code (0x03), Byte Count
            expected_byte_count = 2 * num_registers
            if (len(byte_list) >= expected_byte_count + 5 and
                byte_list[0] == 0x01 and byte_list[1] == 0x03 and
                byte_list[2] == expected_byte_count):
                # Extract data bytes (skip first 3 bytes, last 2 bytes are CRC)
                data_bytes = byte_list[3:3 + expected_byte_count]
                # Convert to 16-bit values
                values = bytes_to_16bit_values(data_bytes)
                # Place values in the registers array
                for i, value in enumerate(values):
                    register_index = current_start_address + i
                    if register_index < len(registers):
                        registers[register_index] = value
                    else:
                        print(f"Warning: Register index {register_index} out of range")
            else:
                print(f"Warning: Invalid response format at address {current_start_address:04x}")
            current_start_address = None  # Reset for the next request
            data_lines = []

# Save only used registers (those that are not 0xFFFF) to a file
with open(output_file_path, 'w') as f:
    for i, value in enumerate(registers):
        if value != 0xFFFF:
            f.write(f"Register {i:04x}: {value:04x}\n")


print(f"Extracted {len(registers)} registers and saved to {output_file_path}")
# Print a sample of non-empty registers (values != 0xFFFF)
print("Sample of extracted registers (non-0xFFFF values):")
sample_count = 0
for i in range(len(registers)):
    if registers[i] != 0xFFFF:
        print(f"Register {i:04x}: {registers[i]:04x}")
        sample_count += 1
        if sample_count >= 32:  # Limit to 32 registers for brevity
            break
if sample_count == 0:
    print("No non-0xFFFF registers found.")