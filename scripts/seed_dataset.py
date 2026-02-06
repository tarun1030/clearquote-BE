"""
Seed ClearQuote dataset files into Postgres.

Designed for Docker usage:
- Waits for Postgres to become reachable
- Creates tables (via SQLAlchemy metadata) if they don't exist
- Loads 4 dataset files into:
    vehicle_cards, damage_detections, repairs, quotes

Default behavior is idempotent: if a table already has rows, it will be skipped.
Set SEED_TRUNCATE=true to TRUNCATE and reload.

Supports CSV out of the box. XLSX is supported if openpyxl is installed.
"""

from __future__ import annotations

import asyncio
import csv
import os
from dataclasses import dataclass
from datetime import datetime, date, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Float, Integer, Numeric

from database import Base, VehicleCard, DamageDetection, Repair, Quote


@dataclass(frozen=True)
class TableSeed:
    table_name: str
    model: Any
    default_filename: str


SEEDS: list[TableSeed] = [
    TableSeed(
        table_name="vehicle_cards",
        model=VehicleCard,
        default_filename="ClearQuote Sample Dataset.xlsx - vehicle_cards.csv",
    ),
    TableSeed(
        table_name="damage_detections",
        model=DamageDetection,
        default_filename="ClearQuote Sample Dataset.xlsx - damage_detections.csv",
    ),
    TableSeed(
        table_name="repairs",
        model=Repair,
        default_filename="ClearQuote Sample Dataset.xlsx - repairs.csv",
    ),
    TableSeed(
        table_name="quotes",
        model=Quote,
        default_filename="ClearQuote Sample Dataset.xlsx - quotes.csv",
    ),
]


def _project_root() -> Path:
    # scripts/seed_dataset.py -> project root
    return Path(__file__).resolve().parents[1]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_async_db_url(db_url: str) -> str:
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


async def _wait_for_db(engine, attempts: int = 60, delay_s: float = 1.0) -> None:
    last_err: Exception | None = None
    for _ in range(attempts):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as e:  # noqa: BLE001 - startup wait loop
            last_err = e
            await asyncio.sleep(delay_s)
    raise RuntimeError(f"Database not reachable after {attempts} attempts: {last_err}") from last_err


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in {"true", "t", "1", "yes", "y"}:
        return True
    if v in {"false", "f", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def _parse_datetime(value: str) -> datetime:
    v = value.strip()
    # Accept "YYYY-MM-DD" or ISO datetime.
    try:
        dt = datetime.fromisoformat(v)
        if isinstance(dt, datetime):
            return dt
    except ValueError:
        pass
    d = date.fromisoformat(v)
    return datetime.combine(d, time.min)


def _coerce_row_for_model(row: dict[str, str], model: Any) -> dict[str, Any]:
    table = model.__table__
    out: dict[str, Any] = {}
    for key, raw in row.items():
        col = table.columns.get(key)
        if col is None:
            continue
        if raw is None:
            out[key] = None
            continue
        s = raw.strip()
        if s == "":
            out[key] = None
            continue

        ctype = col.type
        try:
            if isinstance(ctype, Integer):
                out[key] = int(s)
            elif isinstance(ctype, Float):
                out[key] = float(s)
            elif isinstance(ctype, Boolean):
                out[key] = _parse_bool(s)
            elif isinstance(ctype, Numeric):
                out[key] = Decimal(s)
            elif isinstance(ctype, DateTime):
                out[key] = _parse_datetime(s)
            else:
                out[key] = s
        except Exception as e:  # noqa: BLE001 - add context
            raise ValueError(f"Failed to coerce column {table.name}.{key} from {s!r}") from e

    return out


def _read_csv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # DictReader returns dict[str, str | None]; normalize to str
            yield {k: (v if v is not None else "") for k, v in row.items()}


def _read_xlsx_rows(path: Path) -> Iterable[dict[str, str]]:
    try:
        import openpyxl  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "XLSX seeding requires 'openpyxl'. "
            "Either install it (pip install openpyxl) or export the file to CSV."
        ) from e

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    headers = next(rows_iter, None)
    if not headers:
        return []

    keys = [str(h).strip() for h in headers]
    for r in rows_iter:
        row = {keys[i]: ("" if r[i] is None else str(r[i])) for i in range(len(keys))}
        yield row


def _read_rows(path: Path) -> Iterable[dict[str, str]]:
    if path.suffix.lower() == ".csv":
        return _read_csv_rows(path)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return _read_xlsx_rows(path)
    raise RuntimeError(f"Unsupported dataset file type: {path.name}")


async def _table_row_count(conn, table_name: str) -> int:
    res = await conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
    return int(res.scalar_one())


async def _set_sequence(conn, table_name: str, pk_name: str) -> None:
    # Works for SERIAL/IDENTITY-backed PKs. Safe no-op if no sequence exists.
    await conn.execute(
        text(
            """
            SELECT setval(
              pg_get_serial_sequence(:table, :pk),
              COALESCE((SELECT MAX(%(pk)s) FROM "%(table)s"), 1),
              true
            )
            """
            % {"pk": pk_name, "table": table_name}
        ),
        {"table": table_name, "pk": pk_name},
    )


async def seed() -> None:
    db_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DB_URL (or DATABASE_URL) must be set for seeding.")

    seed_truncate = _env_bool("SEED_TRUNCATE", default=False)
    chunk_size = int(os.getenv("SEED_CHUNK_SIZE", "500"))

    root = Path(os.getenv("SEED_DATA_DIR", str(_project_root())))
    print(f"[seed] Using data directory: {root}")
    print(f"[seed] SEED_TRUNCATE={seed_truncate}, SEED_CHUNK_SIZE={chunk_size}")

    engine = create_async_engine(_to_async_db_url(db_url), echo=False, pool_pre_ping=True)

    try:
        print("[seed] Waiting for Postgres...")
        await _wait_for_db(engine)
        print("[seed] Postgres is reachable.")

        async with engine.begin() as conn:
            print("[seed] Ensuring tables exist (create_all)...")
            await conn.run_sync(Base.metadata.create_all)

            if seed_truncate:
                print("[seed] Truncating tables before load...")
                # Truncate in reverse-ish dependency order; CASCADE handles FKs if present.
                await conn.execute(
                    text(
                        'TRUNCATE TABLE "quotes", "repairs", "damage_detections", "vehicle_cards" RESTART IDENTITY CASCADE'
                    )
                )

            for spec in SEEDS:
                table = spec.model.__table__
                pk_cols = [c.name for c in table.primary_key.columns]
                pk_name = pk_cols[0] if pk_cols else None

                existing = await _table_row_count(conn, spec.table_name)
                if existing > 0 and not seed_truncate:
                    print(f"[seed] Skipping {spec.table_name}: already has {existing} rows.")
                    continue

                env_key = f"SEED_{spec.table_name.upper()}_FILE"
                dataset_path = Path(os.getenv(env_key, str(root / spec.default_filename)))
                if not dataset_path.exists():
                    raise FileNotFoundError(
                        f"Dataset file not found for {spec.table_name}: {dataset_path} "
                        f"(override via {env_key} or SEED_DATA_DIR)"
                    )

                print(f"[seed] Loading {spec.table_name} from {dataset_path.name} ...")
                rows_iter = _read_rows(dataset_path)

                batch: list[dict[str, Any]] = []
                inserted = 0
                for raw_row in rows_iter:
                    coerced = _coerce_row_for_model(raw_row, spec.model)
                    if not coerced:
                        continue
                    batch.append(coerced)
                    if len(batch) >= chunk_size:
                        await conn.execute(table.insert(), batch)
                        inserted += len(batch)
                        batch.clear()

                if batch:
                    await conn.execute(table.insert(), batch)
                    inserted += len(batch)

                print(f"[seed] Inserted {inserted} rows into {spec.table_name}.")

                if pk_name:
                    try:
                        await _set_sequence(conn, spec.table_name, pk_name)
                    except Exception:
                        # Not all schemas will have a serial sequence; ignore.
                        pass

        print("[seed] Done.")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
