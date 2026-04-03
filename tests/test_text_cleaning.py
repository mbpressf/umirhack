from datetime import datetime

from madrigal_assistant.models import RawEvent
from madrigal_assistant.text import clean_public_text, looks_like_promotional_noise


def test_clean_public_text_removes_telegram_reserve_tail() -> None:
    raw_text = (
        "Школьника сбили на пешеходном переходе в Новочеркасске. "
        "Водитель Лады сбила 11-летнего мальчика, его увезли в больницу. "
        "❌ ❌ ❌ С обходами блокировок Телеграм идет борьба. "
        "Дальше блокировки только усилятся! Подпишитесь на РЕЗЕРВ в MAX max.ru/privet_rostov_ru"
    )

    cleaned = clean_public_text(raw_text)

    assert "Школьника сбили" in cleaned
    assert "больницу" in cleaned
    assert "MAX" not in cleaned
    assert "Телеграм идет борьба" not in cleaned
    assert "max.ru" not in cleaned


def test_clean_public_text_removes_max_promo_tail() -> None:
    raw_text = (
        "Школьника сбили на переходе, момент аварии попал на видео. "
        "Объявления работа Купи/продай авто «Блокнот Ростов» в MAX"
    )

    cleaned = clean_public_text(raw_text)

    assert "Школьника сбили" in cleaned
    assert "Купи/продай авто" not in cleaned
    assert "MAX" not in cleaned


def test_clean_public_text_removes_subscribe_max_tail() -> None:
    raw_text = (
        "Эвакуатор устроил транспортный коллапс в Новочеркасске. "
        "Подпишись на @rostov_glavniy Предложи пост Читай MAX"
    )

    cleaned = clean_public_text(raw_text)

    assert cleaned == "Эвакуатор устроил транспортный коллапс в Новочеркасске"


def test_looks_like_promotional_noise_flags_sales_copy() -> None:
    promo_text = (
        "Скидки на тротуарную плитку, большой ассортимент товаров, быстрая доставка, "
        "низкие цены, звоните и заказывайте дизайнерские проекты."
    )
    auto_sale_text = (
        "Брошенный Porsche продан за 960000 рублей, другие авто продают в закрытых перекупских чатах "
        "и перепродают по рыночным ценам. Чат в max."
    )
    issue_text = "Жители Батайска жалуются на запах гари и отключение света в нескольких домах."

    assert looks_like_promotional_noise(promo_text)
    assert looks_like_promotional_noise(auto_sale_text)
    assert not looks_like_promotional_noise(issue_text)


def test_raw_event_validators_clean_title_and_text() -> None:
    event = RawEvent(
        event_id="clean-1",
        url="https://example.com/post/1",
        source_type="social",
        source_name="Telegram / Test",
        published_at=datetime.fromisoformat("2026-04-04T10:00:00+03:00"),
        title="Школьника сбили на переходе. Подпишитесь на РЕЗЕРВ в MAX",
        text=(
            "Школьника сбили на переходе, его увезли в больницу. "
            "❌ ❌ ❌ С обходами блокировок Телеграм идет борьба. "
            "Подпишитесь на РЕЗЕРВ в MAX max.ru/test"
        ),
    )

    assert event.title == "Школьника сбили на переходе"
    assert event.text == "Школьника сбили на переходе, его увезли в больницу"
