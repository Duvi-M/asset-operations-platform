from pydantic import Field, computed_field
from app.schemas.base import AppModel


class ImportRowError(AppModel):
    """Describes a single row that could not be processed."""
    row: int = Field(..., description="Número de fila en el Excel (1-based, con encabezado)")
    identifier: str | None = Field(None, description="Serial / Internal Code extraído (si existe)")
    reason: str = Field(..., description="Motivo por el que la fila fue omitida o generó un error")


class ColumnMapping(AppModel):
    """Reports which Excel column resolved to each logical field."""
    item_name:     str | None = None
    serial_number: str | None = None
    part_number:   str | None = None
    part_desc:     str | None = None   # Import column: PartDescription
    status:        str | None = None
    location:      str | None = None
    size:          str | None = None
    internal_code: str | None = None
    series:        str | None = None   # Import column: Series


class ImportResult(AppModel):
    """Summary returned after processing an Excel import."""

    # File metadata
    filename:          str
    sheet:             str
    available_sheets:  list[str] = Field(default_factory=list)

    # Column detection report
    detected_columns:     ColumnMapping = Field(default_factory=ColumnMapping)
    unrecognised_columns: list[str] = Field(
        default_factory=list,
        description="Columnas del archivo no mapeadas a ningún campo lógico",
    )

    # Counters
    total_rows:       int = Field(0, description="Filas de datos leídas (sin encabezado)")
    parts_created:    int = 0
    parts_reused:     int = 0
    assets_created:   int = 0
    assets_updated:   int = 0
    rows_skipped:     int = 0
    assets_unchanged: int = 0
    status_counts:    dict[str, int] = Field(default_factory=dict)

    # Per-row errors (capped at 500)
    errors: list[ImportRowError] = Field(default_factory=list)

    @computed_field
    @property
    def rows_ok(self) -> int:
        """Rows that resulted in a create or update."""
        return self.assets_created + self.assets_updated

    @computed_field
    @property
    def success(self) -> bool:
        return self.rows_ok > 0 or (self.total_rows > 0 and len(self.errors) == 0)
