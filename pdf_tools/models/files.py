from pathlib import Path

import filetype  # type: ignore
from pydantic import BaseModel, computed_field


class File(BaseModel):
    path_str: str
    bookmark_name: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def path(self) -> Path:
        return Path(self.path_str)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def absolute_path(self) -> Path:
        return self.path.absolute()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def type(self) -> str:
        if self.absolute_path.is_dir():
            return "dir"
        kind = filetype.guess(str(self.absolute_path))
        if kind is None:
            return self.path.suffix

        return kind.extension

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> str:
        return self.path.name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def parent(self) -> Path:
        return self.path.parent
