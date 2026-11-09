"""pytest 공통 준비물(fixture). tests/ 안의 모든 테스트에서 자동으로 쓸 수 있다."""
import pytest

import db
from app import create_app


@pytest.fixture
def app(tmp_path):
    """테스트 전용 앱. 테스트마다 새 임시 DB 파일을 쓴다.

    tmp_path: pytest가 테스트마다 만들어 주는 임시 폴더.
    실제 instance/addressbook.db 는 건드리지 않는다.
    """
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
    })


@pytest.fixture
def client(app):
    """브라우저 대신 요청을 보내는 Flask 테스트 클라이언트."""
    return app.test_client()


@pytest.fixture
def count_contacts(app):
    """임시 DB에 저장된 연락처 수를 세는 함수를 돌려준다."""
    def _count():
        with app.app_context():
            return db.get_db().execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return _count
