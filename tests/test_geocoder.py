"""Unit tests for the batch geocoder."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ffl.ingestion.geocoder import GeocodeResult, geocode_batch, _geocode_chunk


class TestGeocodeChunk:
    def _make_chunk(self, n: int = 3) -> pd.DataFrame:
        return pd.DataFrame([
            {"id": i, "street": f"{i} Main St", "city": "Austin", "state": "TX", "zip": "78701"}
            for i in range(n)
        ])

    def test_returns_result_for_each_row(self):
        chunk = self._make_chunk(3)
        mock_response = [
            {"id": "0", "lat": "30.2672", "lon": "-97.7431", "match": "Match"},
            {"id": "1", "lat": "30.2673", "lon": "-97.7432", "match": "Match"},
            {"id": "2", "lat": None, "lon": None, "match": "No_Match"},
        ]
        with patch("ffl.ingestion.geocoder.cg.addressbatch", return_value=mock_response):
            results = _geocode_chunk(chunk)

        assert len(results) == 3
        assert results[0].matched is True
        assert results[0].lat == pytest.approx(30.2672)
        assert results[1].matched is True
        assert results[2].matched is False
        assert results[2].lat is None

    def test_api_failure_returns_unmatched(self):
        chunk = self._make_chunk(2)
        with patch("ffl.ingestion.geocoder.cg.addressbatch", side_effect=RuntimeError("API down")):
            results = _geocode_chunk(chunk)

        assert len(results) == 2
        assert all(not r.matched for r in results)


class TestGeocodeBatch:
    def _make_addresses(self, n: int) -> pd.DataFrame:
        return pd.DataFrame([
            {"id": i, "street": f"{i} Oak Ave", "city": "Denver", "state": "CO", "zip": "80202"}
            for i in range(n)
        ])

    def test_batches_correctly(self):
        """With batch_size=2 and 5 addresses, should call geocoder 3 times."""
        addresses = self._make_addresses(5)

        call_count = 0
        def mock_batch(buf, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch("ffl.ingestion.geocoder.cg.addressbatch", side_effect=mock_batch):
            with patch("ffl.ingestion.geocoder.settings") as mock_settings:
                mock_settings.geocode_batch_size = 2
                mock_settings.geocode_benchmark = "Public_AR_Current"
                with patch("ffl.ingestion.geocoder.time.sleep"):
                    results = geocode_batch(addresses)

        assert len(results) == 5
        # 5 addresses / 2 per batch = 3 batches
        assert call_count == 3

    def test_all_unmatched_on_failure(self):
        addresses = self._make_addresses(3)
        with patch("ffl.ingestion.geocoder.cg.addressbatch", side_effect=Exception("fail")):
            with patch("ffl.ingestion.geocoder.time.sleep"):
                results = geocode_batch(addresses)

        assert len(results) == 3
        assert all(not r.matched for r in results)

    def test_geocode_result_dataclass(self):
        result = GeocodeResult(
            street="100 Main", city="Test", state="TX", zip="12345",
            lat=30.0, lng=-97.0, matched=True
        )
        assert result.matched is True
        assert result.lat == 30.0
