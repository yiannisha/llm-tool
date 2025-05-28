from llm_tool import llm_tool

import inspect
from dataclasses import dataclass
from typing import Callable, Union, _BaseGenericAlias

@dataclass
class GlobalToolConfig:
    desc_required: bool = False
    return_required: bool = False

class DocStringException(Exception):
    def __init__(self, message: str):
        super().__init__(message)

class TypeParsingException(Exception):
    def __init__(self, message: str):
        super().__init__(message)

class DefinedFunction():

    def __init__(self, func, definition = {}, context = None) -> None:
        """
        A function that has been defined in the llm_tool tool. 
        """

        self._func = func
        self._definition = definition
        self._context = context

    def __call__(self, *args, **kwargs):
        if self._context:
            return self._func(self._context, *args, **kwargs)

        return self._func(*args, **kwargs)

    @property
    def definition(self):
        return self._definition

def get_type_name(type_: Union[type, _BaseGenericAlias, None]) -> str:
    
    # _BaseGenericAlias
    if type_ is str:
        return 'string'
    elif hasattr(type_, '_name'):
        return type_._name
    # implements __name__
    elif hasattr(type_, '__name__'):
        return type_.__name__
    elif type_ is None:
        return 'None'

    raise TypeParsingException(f"Failed to parse type: {type_}")

def tool(context = None, desc_required: Union[bool, None] = None, return_required: Union[bool, None] = None) -> Callable[[Callable], DefinedFunction]:
    desc_required = desc_required if desc_required is not None else GlobalToolConfig.desc_required
    return_required = return_required if return_required is not None else GlobalToolConfig.return_required

    def inner(func: Callable) -> DefinedFunction:
        parsed = None
        if func.__doc__:
            parsed = llm_tool.parse_docstring(func.__doc__)

        params = {
            "type": "object",
            "properties": {}
        }

        if func_params := inspect.signature(func).parameters:

            for key, value in func_params.items():

                if key == 'self':
                    continue

                param_anno: Union[type, _BaseGenericAlias, inspect._empty] = value.annotation
                if param_anno is inspect._empty:
                    raise DocStringException(f"No type found for parameter `{key}` in function `{func.__name__}`")

                is_required: bool = value._default is inspect._empty 

                if desc_required and (not parsed or parsed.params.get(key, None) is None):
                    raise DocStringException(f"Parameter `{key}` description not found in docstring of `{func.__name__}` function signature.")
                
                # param_anno: Union[type, _BaseGenericAlias]
                params["properties"][key] = {
                    "type": get_type_name(param_anno),
                    "description": parsed.params.get(key, "") if parsed else "",
                }

                # add required parameters
                if not isinstance(params.get("required", None), list): params["required"] = [] 
                if is_required:
                    params["required"].append(key)
                else:
                    # add default value in description
                    params["properties"][key]["description"] += f" Default Value: `{value._default}`"
        
        else:
            params = {}

        description = ""
        if parsed:
            description += parsed.description if parsed.description else "" 

            if parsed.returns:
                return_anno = inspect.signature(func).return_annotation    
                # if a function returns None then return_anno is None instead of NoneType
                
                if return_anno is not inspect._empty:
                    return_type = get_type_name(return_anno)
                    description += f"\n\nReturn Type: `{return_type}`"

                elif return_required:
                    raise DocStringException(f"Return type not found in function `{func.__name__}`.")

                description += f"\n\nReturn Description: {parsed.returns}"
            elif return_required:
                raise DocStringException(f"Return description not found in docstring of `{func.__name__}` function signature.")
        elif return_required:
            raise DocStringException(f"Return description not found in docstring of `{func.__name__}` function signature.")

        out = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": params,
            }
        }

        func = DefinedFunction(func, out, context)
        return func

    return inner
