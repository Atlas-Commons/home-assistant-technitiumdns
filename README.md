# TechnetiumDNS Integration for Home Assistant

This custom integration allows you to integrate TechnetiumDNS with Home Assistant, providing sensors for various DNS statistics.

## Installation

### Manual Installation

1. **Download the repository:**
   - Clone the repository or download the ZIP file.
    ```bash
       git clone https://github.com/yourusername/home-assistant-technetiumdns.git
    ```
2. **Copy to Home Assistant:**
   - Copy the `custom_components` directory into your Home Assistant configuration directory.

    ```bash
       cp -r home-assistant-technetiumdns/custom_components/technetiumdns /path/to/your/home-assistant/config/custom_components/
    ```
### HACS Installation

1. **Add Custom Repository:**
   - Go to HACS in your Home Assistant.
   - Click on "Integrations".
   - Click on the three dots in the upper right corner and select "Custom repositories".
   - Add the URL to this repository: https://github.com/Amateur-God/home-assistant-technetiumdns and select the category "Integration".

2. **Install the Integration:**
   - Find `TechnetiumDNS` in HACS and click "Install".

## Configuration

1. **Add the Integration:**
   - Go to Home Assistant Configuration > Integrations.
   - Click on the "+" button to add a new integration.
   - Search for `TechnetiumDNS` and follow the configuration steps.

2. **Configuration via `configuration.yaml`:**

   Add the following to your `configuration.yaml`:

   technetiumdns:
     api_url: "http://your-technetiumdns-url:technitum-port"
     token: "your-api-token"
     username: "your-username"

## Usage

This integration provides sensors for:

- DNS Queries (Last Day)
- Blocked Queries (Last Day)
- Clients (Last Day)
- Top Clients (Last Day)
- Top Domains (Last Day)
- Top Blocked Domains (Last Day)
- No Error (Last Day)
- Server Failure (Last Day)
- NX Domain (Last Day)
- Refused (Last Day)
- Authoritative (Last Day)
- Recursive (Last Day)
- Cached (Last Day)
- Dropped (Last Day)
- Zones (Last Day)
- Cached Entries (Last Day)
- Allowed Zones (Last Day)
- Blocked Zones (Last Day)
- Allow List Zones (Last Day)
- Block List Zones (Last Day)
- Update Available

## Contributing

If you want to contribute to this project, feel free to fork the repository and submit a pull request. Issues and feature requests are also welcome.

## License

This project is licensed under the GPL 3.0 License. See the [LICENSE](LICENSE) file for details.
