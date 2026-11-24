"""Rubric phải đọc được ĐÚNG từ docs/speaking-rubric.md (nguồn sự thật duy nhất)."""
import pytest

from app.speaking.rubric import CRITERIA, load_rubric
from app.speaking.rubric.anchors import ANCHORS_BY_CRITERION
from app.speaking.rubric.loader import RUBRIC_PATH
from app.speaking.rubric.thresholds import load_thresholds


def test_parses_all_four_criteria_and_levels():
    rubric = load_rubric()

    assert set(rubric.criteria) == set(CRITERIA)
    for key in CRITERIA:
        criterion = rubric.criteria[key]
        assert set(criterion.levels) == {1, 2, 3, 4}
        for level in (1, 2, 3, 4):
            descriptor = criterion.at(level)
            # descriptor và gợi ý là thứ hiển thị cho người học — không được rỗng
            assert descriptor.descriptor.strip()
            assert descriptor.suggestion.strip()


def test_labels_match_rubric_scale():
    rubric = load_rubric()
    assert rubric.labels == {
        1: "Emerging", 2: "Developing", 3: "Proficient", 4: "Advanced",
    }
    assert rubric.label_of(3) == "Proficient"


def test_criterion_codes_map_to_expected_keys():
    rubric = load_rubric()
    assert rubric.criteria["fluency"].code == "C1"
    assert rubric.criteria["pronunciation"].code == "C2"
    assert rubric.criteria["grammar_vocab"].code == "C3"
    assert rubric.criteria["coherence_task"].code == "C4"


def test_level_is_clamped():
    """Gọi nhầm mức ngoài thang thì kẹp lại, không nổ."""
    criterion = load_rubric().criteria["fluency"]
    assert criterion.at(0).level == 1
    assert criterion.at(9).level == 4


def test_missing_file_fails_loudly():
    with pytest.raises(FileNotFoundError):
        load_rubric("khong-ton-tai.md")


def test_malformed_rubric_fails_loudly(tmp_path):
    """Rubric hỏng phải nổ ngay lúc nạp, không được chấm với descriptor thiếu."""
    broken = tmp_path / "rubric.md"
    broken.write_text("# Rubric\n\n### C1 — Fluency\n\nkhông có bảng nào\n", encoding="utf-8")

    with pytest.raises(ValueError, match="không đọc được đầy đủ"):
        load_rubric(str(broken))


def test_rubric_file_is_where_loader_expects():
    assert RUBRIC_PATH.exists(), f"Không thấy rubric tại {RUBRIC_PATH}"


def test_anchors_cover_every_level_for_llm_criteria():
    """Rubric mục 7.3 — mỗi mức cần ít nhất một ví dụ neo."""
    for key in ("grammar_vocab", "coherence_task"):
        levels = {a.level for a in ANCHORS_BY_CRITERION[key]}
        assert levels == {1, 2, 3, 4}, f"{key} thiếu anchor cho mức {({1,2,3,4} - levels)}"


def test_coherence_anchors_carry_the_task_prompt():
    """C4 chấm mức bám đề, nên anchor phải có đề bài mới neo đúng."""
    for anchor in ANCHORS_BY_CRITERION["coherence_task"]:
        assert anchor.task.strip()


def test_thresholds_declare_calibration_status():
    """Rubric mục 8: chưa calibrate thì phải tự khai, không im lặng."""
    thresholds = load_thresholds()
    assert "calibrated" in thresholds
    assert isinstance(thresholds["calibrated"], bool)


# ------- Lỗi phát hiện khi chạy trong Docker: rubric nằm NGOÀI package

def test_resolves_rubric_when_running_from_repo():
    from app.speaking.rubric.loader import resolve_rubric_path

    found = resolve_rubric_path()
    assert found is not None and found.is_file()
    assert found.name == "speaking-rubric.md"


def test_env_override_takes_priority(tmp_path, monkeypatch):
    """Container có cấu trúc thư mục khác nên phải trỏ được bằng biến môi trường."""
    from app.speaking.rubric.loader import resolve_rubric_path

    custom = tmp_path / "speaking-rubric.md"
    custom.write_text(RUBRIC_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("SPEAKING_RUBRIC_PATH", str(custom))
    assert resolve_rubric_path() == custom

    load_rubric.cache_clear()
    try:
        assert load_rubric().version == "0.1"
    finally:
        load_rubric.cache_clear()


def test_error_lists_every_path_it_tried(tmp_path, monkeypatch):
    """Thông báo phải chỉ ra đã tìm ở đâu — nếu không thì chỉ biết 'không chấm được'."""
    from app.speaking.rubric import loader

    monkeypatch.setenv("SPEAKING_RUBRIC_PATH", str(tmp_path / "khong-co.md"))
    monkeypatch.setattr(loader, "_candidates", lambda: [tmp_path / "khong-co.md"])

    loader.load_rubric.cache_clear()
    try:
        with pytest.raises(FileNotFoundError) as exc:
            loader.load_rubric()
    finally:
        loader.load_rubric.cache_clear()

    message = str(exc.value)
    assert "khong-co.md" in message
    assert "SPEAKING_RUBRIC_PATH" in message
