"""주소록 앱 테스트. 실행: pytest -v"""
import pytest

import db
from app import create_app


def add_contact(client, **fields):
    """등록 화면(/add)으로 연락처를 저장한다. 빠진 칸은 기본값으로 채운다."""
    data = {"name": "홍길동", "phone": "010-1234-5678",
            "email": "", "address": "", "memo": ""}
    data.update(fields)
    return client.post("/add", data=data)


# 1. 목록 화면
def test_index_ok(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "아직 등록된 연락처가 없습니다" in response.text


# 2. 등록 후 목록에 나타남
def test_add_contact_appears_in_list(client, count_contacts):
    response = add_contact(client, name="홍길동", phone="010-1234-5678",
                           email="hong@example.com")
    # 저장에 성공하면 목록(/)으로 이동한다
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    page = client.get("/").text
    assert "연락처가 등록되었습니다" in page
    assert "홍길동" in page
    assert "010-1234-5678" in page
    assert "hong@example.com" in page
    assert count_contacts() == 1


# 3. 수정하면 값이 바뀜
def test_edit_contact_changes_values(client, app):
    add_contact(client, name="홍길동", phone="010-1234-5678")

    # 수정 화면에는 기존 값이 채워져 있어야 한다
    edit_page = client.get("/edit/1").text
    assert 'value="홍길동"' in edit_page

    response = client.post("/edit/1", data={
        "name": "홍길순", "phone": "010-9999-8888",
        "email": "", "address": "부산", "memo": "",
    })
    assert response.status_code == 302

    page = client.get("/").text
    assert "수정되었습니다" in page
    assert "홍길순" in page
    assert "010-9999-8888" in page
    assert "010-1234-5678" not in page

    # 화면뿐 아니라 DB 값도 바뀌었는지 확인한다
    with app.app_context():
        row = db.get_contact(1)
    assert (row["name"], row["phone"], row["address"]) == ("홍길순", "010-9999-8888", "부산")


# 4. 삭제하면 목록에서 사라짐
def test_delete_contact_removes_from_list(client, count_contacts):
    add_contact(client, name="홍길동", phone="010-1234-5678")
    add_contact(client, name="김해사", phone="010-2222-3333")

    response = client.post("/delete/1")
    assert response.status_code == 302

    page = client.get("/").text
    assert "삭제되었습니다" in page
    assert "홍길동" not in page
    assert "김해사" in page  # 다른 연락처는 남아 있어야 한다
    assert count_contacts() == 1


def test_delete_requires_post(client, count_contacts):
    """GET(주소창 입력, 링크)으로는 삭제되지 않는다."""
    add_contact(client)
    assert client.get("/delete/1").status_code == 405
    assert count_contacts() == 1


# 5. 이름 검색
def test_search_by_name(client):
    add_contact(client, name="홍길동", phone="010-1234-5678")
    add_contact(client, name="김해사", phone="010-2222-3333")

    page = client.get("/", query_string={"q": "길동"}).text
    assert "홍길동" in page
    assert "김해사" not in page


def test_search_no_result(client):
    add_contact(client, name="홍길동")
    page = client.get("/", query_string={"q": "없는사람"}).text
    assert "검색 결과가 없습니다" in page
    assert "홍길동" not in page


# 6. 이름이 비었거나 전화번호 형식이 틀리면 저장되지 않음
@pytest.mark.parametrize("name, phone, message", [
    ("", "010-1234-5678", "이름을 입력해 주세요"),
    ("   ", "010-1234-5678", "이름을 입력해 주세요"),       # 공백만 입력
    ("홍길동", "010-abcd-5678", "숫자와 하이픈"),
    ("홍길동", "010 1234 5678", "숫자와 하이픈"),             # 하이픈 대신 공백
    ("홍길동", "12345", "숫자와 하이픈"),                     # 너무 짧음
    ("홍길동", "", "전화번호를 입력해 주세요"),
], ids=["empty-name", "blank-name", "phone-letters", "phone-spaces", "phone-short", "empty-phone"])
# ids: pytest 결과에 보일 각 경우의 이름 (한글은 \uXXXX 로 깨져 보여서 영어로 붙인다)
def test_invalid_input_is_not_saved(client, count_contacts, name, phone, message):
    response = add_contact(client, name=name, phone=phone, address="서울")
    # 저장되지 않고 폼을 다시 보여 준다 (리다이렉트 아님)
    assert response.status_code == 200
    assert message in response.text
    # 입력했던 다른 값은 폼에 남아 있어야 한다
    assert 'value="서울"' in response.text
    assert count_contacts() == 0


def test_invalid_edit_is_not_saved(client, app):
    add_contact(client, name="홍길동", phone="010-1234-5678")
    response = client.post("/edit/1", data={"name": "", "phone": "010-1234-5678"})
    assert response.status_code == 200
    assert "이름을 입력해 주세요" in response.text
    with app.app_context():
        assert db.get_contact(1)["name"] == "홍길동"  # 원래 값 그대로


# 7. SQL 인젝션 시도: 모든 데이터가 나오면 안 된다
def test_search_sql_injection(client, count_contacts):
    add_contact(client, name="홍길동", phone="010-1234-5678")
    add_contact(client, name="김해사", phone="010-2222-3333")

    page = client.get("/", query_string={"q": "' OR '1'='1"}).text
    assert "홍길동" not in page
    assert "김해사" not in page
    assert "검색 결과가 없습니다" in page
    # 데이터도 그대로 남아 있어야 한다
    assert count_contacts() == 2


# 8. init-db 명령 없이도 앱이 동작함
def test_index_without_init_db(tmp_path):
    """init-db를 실행하지 않은 새 DB 파일로도 목록 화면이 열린다."""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "new.db")})
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert "아직 등록된 연락처가 없습니다" in response.text


def test_data_kept_after_app_restart(tmp_path):
    """앱을 다시 만들어도(서버를 껐다 켠 상황) 저장한 연락처가 남아 있다."""
    config = {"TESTING": True, "DATABASE": str(tmp_path / "restart.db")}
    add_contact(create_app(config).test_client(), name="홍길동", phone="010-1234-5678")

    # 같은 DB 파일로 앱을 새로 만든다. 테이블을 다시 만들면서 데이터가 지워지면 안 된다
    page = create_app(config).test_client().get("/").text
    assert "홍길동" in page
    assert "010-1234-5678" in page
