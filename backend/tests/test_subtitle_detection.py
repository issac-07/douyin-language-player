import pytest

from app.services.pipeline import OCRObservation
from app.services.subtitle_detection import SubtitleDetector, normalized


def detect(values, fps=2, duration=8):
    detector = SubtitleDetector(fps, duration)
    for timestamp, text, confidence in values:
        detector.observe(OCRObservation(timestamp, text, confidence))
    return detector.finish()


def test_duplicates_merge_and_blank_separates_repeated_sentence():
    segments = detect([(0, "", 0), (0.5, "今天我们一起去吃饭", .98), (1, "今天我们一起去吃饭", .98),
                       (1.5, "", 0), (2, "今天我们一起去吃饭", .98), (2.5, "今天我们一起去吃饭", .98), (3, "", 0)])
    assert len(segments) == 2
    assert [(s.start_time, s.end_time) for s in segments] == [(0.5, 1.5), (2, 3)]
    assert segments[0].metadata["observations"] == 2


def test_changes_and_end_of_video_are_timed_on_video_samples():
    segments = detect([(0, "今天我们一起去吃饭", .98), (.5, "今天我们一起去吃饭", .98),
                       (1, "你在干什么？", .98), (1.5, "你在干什么？", .98)], duration=1.8)
    assert [(s.start_time, s.end_time) for s in segments] == [(0, 1), (1, 1.8)]
    assert segments[0].metadata["timestamp_uncertainty"] == .5


def test_temporary_low_confidence_and_near_match_do_not_duplicate():
    segments = detect([(0, "今天我们一起去吃饭", .92), (.5, "不可信", .2),
                       (1, "今天我们一起去吃饭", .92), (1.5, "今天我们一起去吃反", .7),
                       (2, "今天我们一起去吃饭", .92), (2.5, "", 0)])
    assert len(segments) == 1
    assert segments[0].text == "今天我们一起去吃饭"
    assert segments[0].end_time == 2.5


def test_high_confidence_similar_but_different_sentences_stay_separate():
    segments = detect([(0, "今天我去吃饭", .98), (.5, "今天我去吃饭", .98), (1, "今天你去吃饭", .98)])
    assert len(segments) == 2


def test_empty_and_low_confidence_frames_produce_no_subtitles():
    assert detect([(0, "", 0), (.5, "", 0), (1, "错误", .2)]) == []


def test_long_uncertain_gap_does_not_join_later_occurrence():
    segments = detect([(0, "你好", .9), (.5, "错", .2), (1, "错", .2), (1.5, "错", .2), (2, "你好", .9)])
    assert len(segments) == 2
    assert segments[0].end_time == .5


def test_normalization_keeps_chinese_digits_and_removes_punctuation():
    assert normalized("今天 ２０２６ 年！\n你好？") == "今天2026年你好"


@pytest.mark.parametrize('before,after', [
    ('我喜欢你', '我不喜欢你'), ('我不喜欢你', '我喜欢你'),
    ('今天一共100元', '今天一共1000元'), ('今天去北京', '今天去南京'),
    ('今天见李明', '今天见李小明'),
])
def test_confident_insertions_deletions_numbers_and_names(before, after):
    segments = detect([(0, before, .99), (.5, after, .99)])
    assert [s.text for s in segments] == [before, after]
    assert segments[0].end_time == segments[1].start_time == .5


def test_transient_extra_line_is_rejected_but_confirmed_line_keeps_first_timestamp():
    base = '今天我们一起去吃饭'
    extra = '饼\n' + base
    transient = detect([(0, base, .99), (.5, extra, .97), (1, base, .99)])
    assert [s.text for s in transient] == [base]
    confirmed = detect([(0, base, .99), (.5, extra, .97), (1, extra, .97)])
    assert [s.text for s in confirmed] == [base, extra]
    assert confirmed[1].start_time == .5


def test_repeated_moderate_confidence_negation_keeps_first_timestamp():
    values = [(0, '我喜欢你', .9), (.5, '我喜欢你', .9), (1, '我不喜欢你', .9), (1.5, '我不喜欢你', .9)]
    segments = detect(values)
    assert [s.text for s in segments] == ['我喜欢你', '我不喜欢你']
    assert segments[1].start_time == 1
