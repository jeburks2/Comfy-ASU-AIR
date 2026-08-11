import base64
import io
import os

import numpy as np
import requests
import torch
from PIL import Image


API_URL = "https://openai.rc.asu.edu/v1/images/generations"
MODEL = "flux-2-dev"


class ASUAIRImageGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": True,
                        "default": "",
                    },
                ),
                "size": (
                    [
                        "1024x1024",
                        "1536x1024",
                        "1024x1536",
                    ],
                    {
                        "default": "1024x1024",
                    },
                ),
                "output_format": (
                    [
                        "png",
                        "jpeg",
                        "webp",
                    ],
                    {
                        "default": "png",
                    },
                ),
            },
            "optional": {
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                "steps": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 100,
                        "step": 1,
                    },
                ),
                "guidance": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 20.0,
                        "step": 0.1,
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    FUNCTION = "generate"
    CATEGORY = "ASU AI"

    def generate(
        self,
        prompt,
        size,
        output_format,
        seed=0,
        steps=0,
        guidance=0.0,
    ):
        api_key = os.environ.get("ASU_AIR_API_KEY")

        if not api_key:
            raise RuntimeError(
                "ASU_AIR_API_KEY environment variable is not set"
            )

        payload = {
            "model": MODEL,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }

        # Provider-specific FLUX parameters.
        # Only send them when explicitly set.
        if seed:
            payload["seed"] = seed

        if steps:
            payload["num_inference_steps"] = steps

        if guidance:
            payload["guidance_scale"] = guidance

        if output_format:
            payload["output_format"] = output_format

        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=600,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Failed to connect to ASU AIR API: {exc}"
            ) from exc

        if not response.ok:
            raise RuntimeError(
                f"ASU AIR API returned HTTP {response.status_code}:\n"
                f"{response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"ASU AIR API returned invalid JSON:\n"
                f"{response.text}"
            ) from exc

        if not data.get("data"):
            raise RuntimeError(
                f"ASU AIR API returned no image data:\n{data}"
            )

        result = data["data"][0]

        if result.get("b64_json"):
            try:
                image_bytes = base64.b64decode(result["b64_json"])
            except Exception as exc:
                raise RuntimeError(
                    "Failed to decode base64 image"
                ) from exc

        elif result.get("url"):
            try:
                image_response = requests.get(
                    result["url"],
                    timeout=120,
                )
                image_response.raise_for_status()
                image_bytes = image_response.content
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Failed to download generated image: {exc}"
                ) from exc

        else:
            raise RuntimeError(
                f"Unknown image response format:\n{result}"
            )

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise RuntimeError(
                "Generated data could not be decoded as an image"
            ) from exc

        image = np.asarray(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image).unsqueeze(0)

        return (image,)


NODE_CLASS_MAPPINGS = {
    "ASUAIRImageGenerator": ASUAIRImageGenerator,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "ASUAIRImageGenerator": "ASU AIR Image Generator",
}