import logging
import os
import pathlib
import typing
from typing import Any

import pystac
import xarray as xr
import yaml

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class NotebookParameters:

    params: dict[str, tuple[type, Any]]
    cwl_params: dict[str, tuple[type | str, Any]]
    dataset_inputs: list[str]

    def __init__(self, params: dict[str, tuple[type, Any]]):
        self.params = params
        self.make_cwl_params()

    def make_cwl_params(self):
        self.dataset_inputs = []
        self.cwl_params = {}
        for param_name in self.params:
            type_, default = self.params[param_name]
            if type_ is xr.Dataset:
                self.dataset_inputs.append(param_name)
            else:
                self.cwl_params[param_name] = self.cwl_type(type_), default
        if self.dataset_inputs:
            self.cwl_params["product"] = "Directory", None

    @classmethod
    def from_code(cls, code: str) -> "NotebookParameters":
        # TODO run whole notebook up to params cell, not just the params cell!
        # (Because it might use imports etc. from earlier in the notebook.)
        # This will need some tweaking of the parameter extraction -- see
        # comment therein.
        return cls(cls.extract_variables(code))

    @classmethod
    def from_yaml(cls, yaml_content: str | typing.IO) -> "NotebookParameters":
        input_data = yaml.safe_load(yaml_content)
        return cls(
            {
                k: (
                    eval(v["type"], globals(), {"Dataset": xr.Dataset}),
                    v["default"],
                )
                for k, v in input_data.items()
            }
        )

    @classmethod
    def from_yaml_file(cls, path: str | os.PathLike) -> "NotebookParameters":
        with open(path, "r") as fh:
            return cls.from_yaml(fh)

    @classmethod
    def extract_variables(cls, code: str) -> dict[str, tuple[type, Any]]:
        # TODO: just working on a single code block is insufficient:
        # We should execute everything up to the params cell, but only extract
        # variables defined in the params cell.
        exec(code, globals(), locals_ := {})
        return {k: cls.make_param_tuple(locals_[k]) for k in (locals_.keys())}

    @staticmethod
    def make_param_tuple(value: Any) -> tuple[type, Any]:
        return (
            t := type(value),
            value if t in {int, float, str, bool} else None,
        )

    def get_cwl_workflow_inputs(self) -> dict[str, dict[str, Any]]:
        return {
            var_name: self.get_cwl_workflow_input(var_name)
            for var_name in self.params
        }

    def get_cwl_step_inputs(self) -> dict[str, str]:
        return {var_name: var_name for var_name in self.params}

    def get_cwl_commandline_inputs(self) -> dict[str, dict[str, Any]]:
        return {
            var_name: self.get_cwl_commandline_input(var_name)
            for var_name in self.params
        }

    def get_cwl_workflow_input(self, var_name: str) -> dict[str, Any]:
        type_, default_ = self.params[var_name]
        return {
            "type": self.cwl_type(type_),
            "default": default_,
            "doc": var_name,
            "label": var_name,
        }

    def get_cwl_commandline_input(self, var_name: str) -> dict[str, Any]:
        return self.get_cwl_workflow_input(var_name) | {
            "inputBinding": {"prefix": f'--{var_name.replace("_", "-")}'}
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            {
                name: {"type": type_.__name__, "default": default_}
                for name, (type_, default_) in self.params.items()
            }
        )

    def read_params_combined(
        self, cli_args: list[str] | None
    ) -> dict[str, str]:
        params = self.read_params_from_env()
        if cli_args:
            params.update(self.read_params_from_cli(cli_args))
        return params

    def read_params_from_env(self) -> dict[str, str]:
        values = {}
        for param_name, (type_, _) in self.params.items():
            env_var_name = "xce_" + param_name
            if env_var_name in os.environ:
                val = os.environ[env_var_name]
                values[param_name] = (
                    val.lower() not in {"false", "0", ""}
                    if type_ is bool
                    else type_(val)
                )
        return values

    def read_params_from_cli(self, args: list[str]) -> dict[str, str]:
        values = {}
        for param_name, (type_, _) in self.params.items():
            arg_name = "--" + param_name.replace("_", "-")
            if arg_name in args and type_ != xr.Dataset:
                values[param_name] = type_ is bool or type_(
                    args[args.index(arg_name) + 1]
                )
        if "product" in self.cwl_params and "--product" in args:
            self.read_datasets_from_product(
                args[args.index("--product") + 1], values
            )
        return values

    def read_datasets_from_product(
        self, stage_in: pathlib.Path | str, values: dict[str, Any]
    ) -> None:
        stage_in_path = pathlib.Path(stage_in)
        catalog_path = stage_in_path / "catalog.json"
        if not catalog_path.is_file():
            raise RuntimeError(
                f"Stage-in directory {stage_in_path} does not contain a "
                f'"catalog.json" file.'
            )
        catalog = pystac.Catalog.from_file(catalog_path)
        item_links = [link for link in catalog.links if link.rel == "item"]
        expected_names = set(self.dataset_inputs)
        provided_names = {
            pystac.Item.from_file(stage_in_path / link.href).id
            for link in item_links
        }
        if (extra := provided_names - expected_names) != set():
            LOGGER.warning(
                f"Unexpected item(s) in stage-in catalogue: {', '.join(extra)}"
            )
        if (missing := expected_names - provided_names) != set():
            raise RuntimeError(
                f"Expected item(s) missing in stage-in catalogue: "
                f"{', '.join(missing)}"
            )
        for param_name, (type_, _) in self.params.items():
            if type_ is xr.Dataset:
                values[param_name] = self.read_staged_in_dataset(
                    stage_in_path, catalog, param_name
                )

    @staticmethod
    def read_staged_in_dataset(
        stage_in_path: pathlib.Path,
        catalog: pystac.Catalog,
        param_name: str,
    ) -> xr.Dataset:
        item_links = [link for link in catalog.links if link.rel == "item"]
        item = next(
            filter(
                lambda i: i.id == param_name,
                (
                    pystac.Item.from_file(stage_in_path / link.href)
                    for link in item_links
                ),
            )
        )
        asset = next(a for a in item.assets.values() if "data" in a.roles)
        return xr.open_dataset(stage_in_path / asset.href)

    @staticmethod
    def cwl_type(type_: type) -> str:
        try:
            # noinspection PyTypeChecker
            return {
                int: "long",
                float: "double",
                str: "string",
                bool: "boolean",
            }[type_]
        except KeyError:
            raise ValueError(f"Unhandled type {type_}")
