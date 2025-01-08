import builtins
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
    def from_yaml(cls, yaml_string: str) -> "NotebookParameters":
        input_data = yaml.safe_load(yaml_string)
        return cls(
            {k: (eval(v["type"]), v["default"]) for k, v in input_data.items()}
        )

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

    def process_arguments(self, args: list[str]) -> dict[str, str]:
        values = {}
        for param_name, (type_, _) in self.params.items():
            arg_name = "--" + param_name.replace("_", "-")
            if arg_name in args:
                values[param_name] = type_(args[args.index(arg_name) + 1])
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
