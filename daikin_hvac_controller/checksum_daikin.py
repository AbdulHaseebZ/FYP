def compute_checksum(packet_str):
    """
    Computes the checksum for a Daikin HVAC command packet given 15 nibbles.
    
    The packet_str is a space-separated string of 15 binary nibbles (4 bits each).
    The function computes the checksum based on these nibbles and returns it as a
    4-bit binary string.
    
    :param packet_str: str, space-separated binary nibbles (e.g., "0001 1000 0001 1000 0000 0000 0001 0000 0010 0000 0101 0000 0000 1000")
    :return: str, the computed checksum binary string
    """
    # Split the space-separated binary string into nibbles
    nibbles = packet_str.split()
    if len(nibbles) != 15:
        raise ValueError("Packet must have exactly 15 nibbles")
    
    # Function to bit-reverse a 4-bit binary string
    def bit_reverse(nibble_bin):
        return nibble_bin[::-1]
    
    # Get logical values for the 15 nibbles
    logical_values = []
    for nib in nibbles:
        reversed_bin = bit_reverse(nib)
        logical_val = int(reversed_bin, 2)
        logical_values.append(logical_val)
    
    # Sum the logical values
    total_sum = sum(logical_values)
    
    # Logical checksum: sum % 16
    logical_checksum = total_sum % 16
    
    # Bit-reverse the logical checksum to get raw checksum
    raw_checksum_bin = bit_reverse(f"{logical_checksum:04b}")
    
    print(f"Computed checksum: {raw_checksum_bin}")
    return raw_checksum_bin

# Example usage with the provided data
packet = "0001100000000000101001000100000010000000000001010000000000001011"
compute_checksum(packet)