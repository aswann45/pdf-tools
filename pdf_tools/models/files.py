from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, RootModel, computed_field


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
        return self.path.resolve()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def type(self) -> str:
        if self.absolute_path.is_dir():
            return "dir"
        return self.path.suffix.replace(".", "")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> str:
        return self.path.name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def parent(self) -> Path:
        return self.path.parent


class Files(RootModel):
    root: Sequence[File]

    def __iter__(self) -> Any:
        return iter(self.root)

    def __getitem__(self, item: Any) -> Any:
        return self.root[item]
