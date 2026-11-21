import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fuentes.indec_series import download_series, search_series


class IndecConnectorTests(unittest.TestCase):
    @patch("fuentes.indec_series._get_json")
    def test_search_returns_catalog_metadata(self, get_json):
        get_json.return_value = {
            "data": [{
                "field": {"id": "123_SERIE", "description": "Producción metalúrgica",
                          "frequency": "R/P1M", "units": "Índice"},
                "dataset": {"title": "IPI manufacturero", "publisher": {"name": "INDEC"}}
            }]
        }
        result = search_series("metalurgia")
        self.assertEqual(result[0]["id"], "123_SERIE")
        self.assertEqual(result[0]["publisher"], "INDEC")

    @patch("fuentes.indec_series.urlopen")
    def test_download_saves_csv_and_provenance(self, urlopen):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b"indice_tiempo,serie_a\n2025-01-01,100.2\n"
        urlopen.return_value = Response()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ipi.csv"
            metadata = download_series(["serie_a"], output)
            self.assertIn("2025-01-01", output.read_text(encoding="utf-8"))
            saved = json.loads(Path(str(output) + ".metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["series_ids"], ["serie_a"])
            self.assertEqual(metadata["data_file"], "ipi.csv")

    def test_rejects_empty_ids(self):
        with self.assertRaises(ValueError):
            download_series([], Path("no-escribe.csv"))


if __name__ == "__main__":
    unittest.main()
