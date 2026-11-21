"""Conector de solo lectura para la API oficial de Series de Tiempo de Argentina."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://apis.datos.gob.ar/series/api"
SOURCE_NAME = "API de Series de Tiempo - Datos Argentina"


def _get_json(url: str, timeout: int = 30) -> dict:
    request = Request(url, headers={"User-Agent": "SIAI-research/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"No se pudo consultar la API oficial: {exc}") from exc


def search_series(query: str, limit: int = 20) -> list[dict]:
    if not query.strip():
        raise ValueError("La búsqueda no puede estar vacía.")
    params = urlencode({"q": query, "limit": max(1, min(limit, 100))})
    payload = _get_json(f"{BASE_URL}/search?{params}")
    results = []
    for item in payload.get("data", []):
        field = item.get("field") or {}
        dataset = item.get("dataset") or {}
        series_id = field.get("id")
        if series_id:
            publisher = dataset.get("publisher") or {}
            results.append({
                "id": series_id,
                "description": field.get("description"),
                "frequency": field.get("frequency"),
                "units": field.get("units"),
                "dataset": dataset.get("title"),
                "publisher": publisher.get("name"),
            })
    return results


def download_series(series_ids: list[str], output: Path, start_date: str | None = None,
                    end_date: str | None = None) -> dict:
    ids = [value.strip() for value in series_ids if value.strip()]
    if not ids:
        raise ValueError("Debe indicarse al menos un identificador de serie.")
    if len(ids) > 40:
        raise ValueError("La API admite hasta 40 series por consulta.")
    params = {"ids": ",".join(ids), "format": "csv"}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    url = f"{BASE_URL}/series?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "SIAI-research/0.1"})
    try:
        with urlopen(request, timeout=60) as response:
            content = response.read().decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"No se pudieron descargar las series oficiales: {exc}") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    metadata = {
        "source": SOURCE_NAME, "source_url": url,
        "catalog_url": "https://api.indec.gob.ar/",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "series_ids": ids, "start_date": start_date, "end_date": end_date,
        "data_file": output.name, "format": "CSV",
        "license_note": "Consultar la licencia del conjunto y citar la fuente primaria."
    }
    output.with_suffix(output.suffix + ".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Conector SIAI para series estadísticas oficiales")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("buscar")
    search.add_argument("texto")
    search.add_argument("--limite", type=int, default=20)
    fetch = sub.add_parser("descargar")
    fetch.add_argument("--ids", required=True)
    fetch.add_argument("--desde")
    fetch.add_argument("--hasta")
    fetch.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "buscar":
            print(json.dumps(search_series(args.texto, args.limite), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(download_series(args.ids.split(","), args.salida, args.desde, args.hasta),
                             ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
