# Comfy-ASU-AIR

Custom ComfyUI nodes for generating and editing images through the ASU AIR API hosted by ASU Research Computing.

## Included Nodes

- **ASU AIR Image Generator**
  - Creates images from text prompts using the ASU AIR image generation endpoint.
- **ASU AIR Image Editor**
  - Edits an input image (optionally with a mask) using prompt-guided image editing.

Both nodes currently target the `flux-2` model exposed by the ASU AIR API.

## Prerequisites

- A working ComfyUI installation
- Active connection to the ASU network through [Cisco VPN](https://docs.rc.asu.edu/sslvpn) (required for API access)
- An **ASU AIR API key**

### How to Request an ASU AIR API Key

API keys are managed through the Voyager Account Management portal.

1. Login to the [Voyager Account Management portal](https://voyager.rc.asu.edu) (Cisco VPN connection required) with your ASURITE credentials.
2. Navigate to the LLM Access tab.
3. Click Create Key to generate an API key.
4. Save this key securely.

See the [API Key Documentation](https://docs.rc.asu.edu/ai/api) for more information on managing your API key.

## Installation

1. Go to your ComfyUI `custom_nodes` directory.
2. Clone this repository:

    ```bash
    cd /path/to/ComfyUI/custom_nodes
    git clone https://github.com/jeburks2/Comfy-ASU-AIR.git
    ```

3. Restart ComfyUI.

### Configure Your API Key In ComfyUI

These nodes expect an environment variable named `ASU_AIR_API_KEY`.

In ComfyUI, configure it directly in your instance settings:

1. Open **Instance Settings**.
2. Go to **Startup Args**.
3. Add an environment variable:

    ```text
    ASU_AIR_API_KEY=your_api_key_here
    ```

4. Save settings and restart the ComfyUI instance.

## Usage Notes

- The nodes appear in ComfyUI under the **ASU AIR** category.
- If `ASU_AIR_API_KEY` is missing, the nodes raise an error at runtime.
- The generator supports output formats: `png`, `jpeg`, and `webp`.
- The editor accepts an optional `MASK` input for inpainting-style workflows.

## Troubleshooting

- **`ASU_AIR_API_KEY environment variable is not set`**
  - Confirm it is set in **Instance Settings** -> **Startup Args** for the running instance.
- **HTTP errors from the API**
  - Confirm [Cisco VPN](https://docs.rc.asu.edu/sslvpn) is connected before running the workflow.
  - Verify your key is valid and active per the [ASU AIR docs](https://docs.rc.asu.edu/ai/api)
  - Check prompt/parameter values and try again.
- **Node not visible in ComfyUI**
  - Confirm repository path is under `ComfyUI/custom_nodes/` and restart ComfyUI.

## Disclaimer

This project is an integration layer for ComfyUI and ASU AIR APIs. API behavior, model availability, limits, and authentication policies are controlled by ASU Research Computing. 

[Research Computing Policies](https://links.asu.edu/policy)

[Research Computing Documentation](https://docs.rc.asu.edu/)

[Research Computing Support](https://links.asu.edu/rc-support)
