from pydantic import BaseModel

class ExampleCreateDTO(BaseModel):
    id: str
    name: str

class ExampleResponseDTO(BaseModel):
    id: str
    name: str