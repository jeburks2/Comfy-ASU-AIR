import base64
import io
import os

import numpy as np
import requests
import torch
from PIL import Image


API_URL = "https://openai.rc.asu.edu/v1/images/edits"
MODEL = "flux-2"


def tensor_to_png(image):
    """Convert a ComfyUI IMAGE tensor to PNG bytes."""
    image = image[0].detach().cpu().numpy()
    image = np.clip(image * 255.0, 0, 255).astype(np.uint8)

    pil_image = Image.fromarray(image)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


def mask_to_png(mask):
    """Convert a ComfyUI MASK tensor to PNG bytes."""
    if mask.ndim == 3:
        mask = mask[0]

    mask = mask.detach().cpu().numpy()
    mask = np.clip(mask * 255.0, 0, 255).astype(np.uint8)

    pil_mask = Image.fromarray(mask, mode="L")

    buffer = io.BytesIO()
    pil_mask.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


class ASUAIRImageEditor:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
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
            },
            "optional": {
                "mask": ("MASK",),
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
                        "max": 100.0,
                        "step": 0.1,
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    FUNCTION = "edit"
    CATEGORY = "ASU AIR"

    def edit(
        self,
        image,
        prompt,
        size,
        mask=None,
        seed=0,
        steps=0,
        guidance=0.0,
    ):
        api_key = os.environ.get("ASU_AIR_API_KEY")

        if not api_key:
            raise RuntimeError(
                "ASU_AIR_API_KEY environment variable is not set"
            )

        image_buffer = tensor_to_png(image)

        files = {
            "image": (
                "image.png",
                image_buffer,
                "image/png",
            ),
        }

        if mask is not None:
            mask_buffer = mask_to_png(mask)
            files["mask"] = (
                "mask.png",
                mask_buffer,
                "image/png",
            )

        data = {
            "model": MODEL,
            "prompt": prompt,
            "n": "1",
            "size": size,
            "response_format": "b64_json",
        }

        # Provider-specific FLUX parameters.
        # Only send them when explicitly enabled.
        if seed:
            data["seed"] = str(seed)

        if steps:
            data["steps"] = str(steps)

        if guidance:
            data["guidance"] = str(guidance)

        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                data=data,
                files=files,
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
            result = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"ASU AIR API returned invalid JSON:\n"
                f"{response.text}"
            ) from exc

        if not result.get("data"):
            raise RuntimeError(
                f"ASU AIR API returned no image data:\n{result}"
            )

        image_result = result["data"][0]

        if image_result.get("b64_json"):
            try:
                image_bytes = base64.b64decode(
                    image_result["b64_json"]
                )
            except Exception as exc:
                raise RuntimeError(
                    "Failed to decode base64 image from ASU AIR API"
                ) from exc

        elif image_result.get("url"):
            try:
                image_response = requests.get(
                    image_result["url"],
                    timeout=120,
                )
                image_response.raise_for_status()
                image_bytes = image_response.content
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Failed to download edited image from ASU AIR API: {exc}"
                ) from exc

        else:
            raise RuntimeError(
                f"Unknown image response format from ASU AIR API:\n{image_result}"
            )

        try:
            edited_image = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")
        except Exception as exc:
            raise RuntimeError(
                "Returned data from ASU AIR API could not be decoded as an image"
            ) from exc

        edited_image = (
            np.asarray(edited_image).astype(np.float32) / 255.0
        )

        edited_image = torch.from_numpy(
            edited_image
        ).unsqueeze(0)

        return (edited_image,)


NODE_CLASS_MAPPINGS = {
    "ASUAIRImageEditor": ASUAIRImageEditor,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "ASUAIRImageEditor": "ASU AIR Image Editor",
}