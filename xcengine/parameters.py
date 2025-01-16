import builtins
import os
import typing
from typing import Any

import yaml


class NotebookParameters:

    params: dict[str, tuple[type, Any]]

    def __init__(self, params: dict[str, tuple[type, Any]]):
        self.params = params

    @classmethod
    def from_code(cls, code: str) -> "NotebookParameters":
        return cls(cls.extract_variables(code))

    @classmethod
    def from_yaml(cls, yaml_content: str | typing.IO) -> "NotebookParameters":
        input_data = yaml.safe_load(yaml_content)
        return cls(
            {k: (eval(v["type"]), v["default"]) for k, v in input_data.items()}
        )

    @classmethod
    def from_yaml_file(cls, path: str | os.PathLike) -> "NotebookParameters":
        with open(path, "r") as fh:
            return cls.from_yaml(fh)

    @staticmethod
    def extract_variables(code: str) -> dict[str, tuple[type, Any]]:
        _old_locals = set(locals().keys())
        exec(code)
        newvars = locals().keys() - _old_locals - {"_old_locals"}
        return {k: (type(v := locals()[k]), v) for k in newvars}

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
            "inputBinding": {"prefix": f"--{var_name.replace("_", "-")}"}
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
            if arg_name in args:
                values[param_name] = type_ is bool or type_(
                    args[args.index(arg_name) + 1]
                )
        return values

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
