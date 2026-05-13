class VisionService:
    async def analyze_image(self, image_path: str) -> dict[str, object]:
        raise NotImplementedError("Wire this to a local CV model or OpenCV pipeline.")
