from dataclasses import dataclass, field


@dataclass
class ToolSpec:
    bin: str = ""
    type: str = "github_release"  # "github_release" | "url_release" | "installer"
    version: str = "latest"
    version_cmd: list[str] = field(default_factory=list)
    version_regex: str = r"(\S+)"
    # binary release 共通 (github_release / url_release)
    platforms: dict[str, str] = field(default_factory=dict)
    extract: str = ""
    opt_dir: str = ""
    bin_path_in_archive: str = ""
    strip_components: int = 1
    extra_bins: list[str] = field(default_factory=list)
    # github_release 専用
    repo: str = ""
    # url_release 専用
    version_url: str = ""
    version_url_regex: str = ""
    # installer 専用
    url: str = ""
    command: str = ""
    update_command: str = ""

    def __post_init__(self) -> None:
        if not self.version_cmd:
            self.version_cmd = [self.bin, "--version"]
        if not self.extract:
            self.extract = self._infer_extract()

    def _infer_extract(self) -> str:
        if not self.platforms:
            return "raw_binary"
        filename = next(iter(self.platforms.values()))
        if filename.endswith((".tar.gz", ".tar.xz")):
            return "tar" if self.opt_dir else "tar_binary"
        if filename.endswith(".gz"):
            return "gz_binary"
        if filename.endswith(".zip"):
            return "zip_binary"
        return "raw_binary"

    @classmethod
    def from_dict(cls, d: dict) -> "ToolSpec":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})
