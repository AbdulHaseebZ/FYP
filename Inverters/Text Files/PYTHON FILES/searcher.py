import re

# Path to the registers file
registers_file_path = "D:\\FYP\\PYTHON FILES\\modbus_registers.txt"

# Load the registers from the file
def load_registers(file_path):
    registers = [0xFFFF] * 861  # Initialize with 0xFFFF for 861 registers
    try:
        with open(file_path, 'r') as f:
            for line in f:
                match = re.match(r'Register\s+([0-9a-fA-F]{4}):\s+([0-9a-fA-F]{4})', line.strip())
                if match:
                    address = int(match.group(1), 16)
                    value = int(match.group(2), 16)
                    if address < len(registers):
                        registers[address] = value
                    else:
                        print(f"Warning: Register address {address:04x} out of range")
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None
    return registers

# Search for values within tolerance
def search_registers(registers, target_value, scaling_factor, tolerance=10):
    if scaling_factor <= 0:
        print("Error: Scaling factor must be positive")
        return []
    # Convert the target value to raw register value
    raw_target = int(target_value / scaling_factor)
    lower_bound = raw_target - tolerance
    upper_bound = raw_target + tolerance
    # Find addresses where register values are within the tolerance range
    matching_addresses = [
        i for i, value in enumerate(registers)
        if lower_bound <= value <= upper_bound and value != 0xFFFF
    ]
    return matching_addresses

# Main interactive loop
def main():
    # Load the registers
    registers = load_registers(registers_file_path)
    if registers is None:
        print("Exiting due to error loading registers")
        return

    while True:
        print("\nModbus Register Search")
        print("Enter 'exit' at any prompt to quit")
        # Get user input
        value_input = input("Enter the value to search (e.g., 240.2 for volts): ")
        if value_input.lower() == 'exit':
            print("Exiting program")
            break
        try:
            target_value = float(value_input)
        except ValueError:
            print("Error: Please enter a valid decimal number or 'exit'")
            continue

        scaling_input = input("Enter the scaling factor (e.g., 0.1 if 240.2 is stored as 2402): ")
        if scaling_input.lower() == 'exit':
            print("Exiting program")
            break
        try:
            scaling_factor = float(scaling_input)
        except ValueError:
            print("Error: Please enter a valid scaling factor or 'exit'")
            continue

        # Optional: Allow user to specify tolerance, default to 10
        tolerance_input = input("Enter tolerance (default 10, press Enter to use default): ")
        if tolerance_input.lower() == 'exit':
            print("Exiting program")
            break
        try:
            tolerance = int(tolerance_input) if tolerance_input.strip() else 10
        except ValueError:
            print("Error: Please enter a valid integer for tolerance or 'exit'")
            continue

        # Perform the search
        matching_addresses = search_registers(registers, target_value, scaling_factor, tolerance)
        
        # Display results
        if matching_addresses:
            print(f"\nFound {len(matching_addresses)} register(s) matching {target_value} "
                  f"(raw value {target_value/scaling_factor:.1f} ± {tolerance}):")
            for addr in matching_addresses:
                print(f"Register {addr:04x}: {registers[addr]:04x} "
                      f"(scaled: {registers[addr] * scaling_factor:.1f})")
        else:
            print(f"\nNo registers found matching {target_value} "
                  f"(raw value {target_value/scaling_factor:.1f} ± {tolerance})")

if __name__ == "__main__":
    main()