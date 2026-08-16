import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

from my_project.api.api_models import BasicComicResponse, ComicMetadataResponse
from my_project.config.config_manager import ConfigManager
from my_project.database.gui_repo_worker import RepoWorker


def create_app(config_man: ConfigManager) -> FastAPI:
    app = FastAPI(title="Comic Server")

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/library")
    def get_library_structure():
        comics_root = config_man.comics_root
        items = []
        for entry in sorted(os.listdir(comics_root)):
            if entry[0] == "0":
                continue
            full_path = os.path.join(comics_root, entry)
            if entry[0] != "." and os.path.isdir(full_path):
                items.append({"name": entry, "type": "folder", "pub_id": entry[0]})

        return items

    @app.get("/folder/{folder_int}", response_model=list[BasicComicResponse])
    def get_folder_contents(folder_int: int) -> list[BasicComicResponse]:
        with RepoWorker(config_man) as worker:
            contents = worker.get_folder_info(folder_int)

        return [
            BasicComicResponse(
                primary_id=comic.primary_id,
                title=comic.title,
                cover_url=f"/comics/{comic.primary_id}/cover",
                download_url=f"/comics/{comic.primary_id}/download",
            )
            for comic in contents
        ]

    @app.get("/comics/{comic_id}/cover")
    def get_cover_image(comic_id: str, size: str = "t"):
        cover_base = config_man.comics_root / ".covers"
        filename = f"{comic_id}_{size}.jpg"
        cover_path = cover_base / filename
        return FileResponse(cover_path, media_type="image/jpeg")

    @app.get("/comics/{comic_id}/metadata", response_model=ComicMetadataResponse)
    def get_metadata(comic_id: str) -> ComicMetadataResponse:
        with RepoWorker(config_man) as worker:
            metadata = worker.get_complete_metadata(comic_id)

        return ComicMetadataResponse.from_metadata(metadata)

    @app.get("/comics/{comic_id}/download")
    def download_comic(comic_id: str):
        with RepoWorker(config_man) as worker:
            partial_path = worker.get_filepath(comic_id)
        if partial_path is None:
            return
        path = config_man.comics_root / partial_path

        def iterfile():
            with open(path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={comic_id}.cbz"},
        )

    return app
