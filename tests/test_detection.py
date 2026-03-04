# CHANGED: pytest Unit-Tests für nms() und smooth_boxes()
import pytest
from detection import DetectionEngine

@pytest.mark.parametrize("boxes,expected_len", [
    ([],                          0),
    ([(0,0,50,50)],               1),
    ([(0,0,50,50),(5,5,50,50)],   1),  # starke Überlappung → eine Box
    ([(0,0,50,50),(100,100,50,50)], 2), # keine Überlappung → beide bleiben
    ([(0,0,50,50),(0,0,50,50)],   1),  # identische Boxen
])
def test_nms(boxes, expected_len):
    result = DetectionEngine.nms(boxes)
    assert len(result) == expected_len

@pytest.mark.parametrize("new,old,alpha", [
    ([],                  [(10,10,50,50)], 0.25),   # neue leer → leeres Ergebnis
    ([(10,10,50,50)],     [],              0.25),   # alte leer → neue übernommen
    ([(10,10,50,50)],     [(10,10,50,50)], 0.25),   # identisch
    ([(100,100,50,50)],   [(10,10,50,50)], 1.0),    # alpha=1 → komplett neue Box
])
def test_smooth_boxes(new, old, alpha):
    result = DetectionEngine.smooth_boxes(new, old, alpha)
    assert len(result) == len(new)
    if new and old and alpha == 1.0:
        assert result[0] == new[0]
