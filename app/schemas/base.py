from pydantic import BaseModel, ConfigDict


class AppModel(BaseModel):
    """Base for all schemas: enables ORM mode and strips leading/trailing whitespace."""

    model_config = ConfigDict(
        from_attributes=True,    # ORM mode
        str_strip_whitespace=True,
        populate_by_name=True,
    )
