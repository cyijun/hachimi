# server.py
from mcp.server.fastmcp import FastMCP
from wakeonlan import send_magic_packet
# Initialize the server with a name
mcp = FastMCP("wake_on_lan_server")

@mcp.tool()
def wake_up(mac_address: str) -> str:
    """Wake up a device using its MAC address."""
    send_magic_packet(mac_address)
    return f"Magic packet sent to {mac_address}."

if __name__ == "__main__":
    # Run the server using the standard input/output transport
    mcp.run(transport="stdio")
