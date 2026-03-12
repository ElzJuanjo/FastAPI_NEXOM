from fastapi import APIRouter, Depends

from app.dto.example_dto import ExampleCreateDTO
from app.use_cases.example_create import CreateExample

from interfaces.dependencies.example_dependencies import (
    get_create_example_use_case
)


router = APIRouter()


@router.post("/examples")
def create_example_endpoint(
    data: ExampleCreateDTO,
    use_case: CreateExample = Depends(get_create_example_use_case)
):

    example = use_case.execute(
        id=data.id,
        name=data.name
    )

    return {
        "id": example.id,
        "name": example.name
    }