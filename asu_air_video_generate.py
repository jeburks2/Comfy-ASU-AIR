import os
import re
import time

import requests

import comfy.model_management
import comfy.utils
import folder_paths
from comfy_api.input_impl import VideoFromFile

from .asu_air_image_edit import tensor_to_png


API_URL = "https://openai.rc.asu.edu/v1/videos"
MODEL = "wan-2-2"


class ASUAIRVideoGenerator:
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
                "seconds": (
                    "INT",
                    {
                        "default": 4,
                        "min": 1,
                        "max": 60,
                    },
                ),
                "size": (
                    "STRING",
                    {
                        "default": "1280x704",
                    },
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                # Not sent to the API — only busts ComfyUI's output cache
                # so re-queueing generates a new video instead of returning
                # the cached one.
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                "poll_interval": (
                    "FLOAT",
                    {
                        "default": 10.0,
                        "min": 1.0,
                        "max": 120.0,
                    },
                ),
                "timeout": (
                    "INT",
                    {
                        "default": 1800,
                        "min": 60,
                        "max": 21600,
                    },
                ),
            },
        }

    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)

    FUNCTION = "generate"
    CATEGORY = "ASU AIR"

    def generate(
        self,
        prompt,
        seconds,
        size,
        image=None,
        seed=0,
        poll_interval=10.0,
        timeout=1800,
    ):
        api_key = os.environ.get("ASU_AIR_API_KEY")

        if not api_key:
            raise RuntimeError(
                "ASU_AIR_API_KEY environment variable is not set"
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        fields = {
            "model": MODEL,
            "prompt": prompt,
            "seconds": str(seconds),
            "size": size,
        }

        # Without an input image the endpoint runs text-to-video (JSON
        # body); with one it runs image-to-video (multipart form with an
        # input_reference file).
        try:
            if image is None:
                response = requests.post(
                    API_URL,
                    headers=headers,
                    json=fields,
                    timeout=120,
                )
            else:
                image_buffer = tensor_to_png(image)
                response = requests.post(
                    API_URL,
                    headers=headers,
                    data=fields,
                    files={
                        "input_reference": (
                            "input.png",
                            image_buffer,
                            "image/png",
                        ),
                    },
                    timeout=180,
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

        job = response.json()
        job_id = job["id"]

        # Video jobs are asynchronous: poll until the render completes,
        # forwarding progress to ComfyUI's progress bar. A 4-second clip
        # takes on the order of 5 minutes, so transient network errors
        # are tolerated rather than abandoning a render in flight.
        progress = comfy.utils.ProgressBar(100)
        deadline = time.monotonic() + timeout
        status = job.get("status", "queued")
        consecutive_failures = 0

        while status not in ("completed", "failed"):
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"ASU AIR video job {job_id} timed out after "
                    f"{timeout}s (last status: {status})"
                )

            time.sleep(poll_interval)
            comfy.model_management.throw_exception_if_processing_interrupted()

            try:
                response = requests.get(
                    f"{API_URL}/{job_id}",
                    headers=headers,
                    timeout=120,
                )
            except requests.RequestException as exc:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    raise RuntimeError(
                        f"Lost connection to ASU AIR API while polling "
                        f"job {job_id}: {exc}"
                    ) from exc
                continue

            if not response.ok:
                raise RuntimeError(
                    f"ASU AIR API returned HTTP {response.status_code}:\n"
                    f"{response.text}"
                )

            consecutive_failures = 0
            job = response.json()
            status = job.get("status", "")
            progress.update_absolute(int(job.get("progress") or 0))

        if status == "failed":
            raise RuntimeError(
                f"ASU AIR video job {job_id} failed: {job.get('error')}"
            )

        try:
            response = requests.get(
                f"{API_URL}/{job_id}/content",
                headers=headers,
                timeout=600,
            )
        except requests.RequestException:
            time.sleep(5)
            try:
                response = requests.get(
                    f"{API_URL}/{job_id}/content",
                    headers=headers,
                    timeout=600,
                )
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Failed to download ASU AIR video job {job_id}: {exc}"
                ) from exc

        if not response.ok:
            raise RuntimeError(
                f"ASU AIR API returned HTTP {response.status_code}:\n"
                f"{response.text}"
            )

        if not response.content:
            raise RuntimeError(
                f"ASU AIR video job {job_id} returned an empty file"
            )

        progress.update_absolute(100)

        output_dir = folder_paths.get_temp_directory()
        os.makedirs(output_dir, exist_ok=True)

        # Job ids are base64 and may contain characters invalid in
        # filenames.
        safe_id = re.sub(r"[^A-Za-z0-9]", "", job_id)[-16:]
        video_path = os.path.join(output_dir, f"asu_air_{safe_id}.mp4")

        with open(video_path, "wb") as f:
            f.write(response.content)

        metadata = {
            "job_id": job_id,
            "model": job.get("model", MODEL),
            "seconds": str(job.get("seconds", seconds)),
            "size": job.get("size", size),
        }

        return {
            "ui": {"asu_air_video": [metadata]},
            "result": (VideoFromFile(video_path),),
        }


NODE_CLASS_MAPPINGS = {
    "ASUAIRVideoGenerator": ASUAIRVideoGenerator,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "ASUAIRVideoGenerator": "ASU AIR Video Generator",
}
