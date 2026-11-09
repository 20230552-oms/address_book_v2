import os
import re

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db


def create_app(test_config=None):
    """Flask 앱을 만들어 돌려주는 앱 팩토리 함수.

    test_config: 테스트할 때 설정(예: 임시 DB 경로)을 바꿔 끼우기 위한 값
    """
    app = Flask(__name__)
    # 기본 설정: DB 파일은 instance/addressbook.db
    app.config.from_mapping(
        # flash 메시지(세션)에 필요한 비밀키. 실제 배포 때는 환경변수로 넣는다
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE=os.path.join(app.instance_path, "addressbook.db"),
    )
    if test_config is not None:
        app.config.update(test_config)

    # instance 폴더가 없으면 만든다 (DB 파일이 이 안에 생긴다)
    os.makedirs(app.instance_path, exist_ok=True)

    # DB 연결 정리와 init-db 명령을 앱에 등록한다
    db.init_app(app)

    # 앱이 켜질 때 테이블이 없으면 만든다 (IF NOT EXISTS라서 기존 데이터는 그대로 남는다)
    with app.app_context():
        db.init_db()

    @app.route("/")
    def index():
        # 목록 화면: 이름순으로 보여 준다. 주소에 ?q=검색어 가 있으면 검색 결과만 보여 준다
        q = request.args.get("q", "").strip()
        contacts = db.list_contacts(q)
        return render_template("index.html", contacts=contacts, q=q)

    @app.route("/add", methods=["GET", "POST"])
    def add():
        # GET: 빈 폼을 보여 준다 / POST: 입력값을 저장한다
        if request.method == "POST":
            form, errors = read_form()
            if errors:
                # 입력한 값을 그대로 다시 보여 준다
                return render_template("form.html", title="새 연락처",
                                       form=form, errors=errors)

            db.create_contact(*to_db_values(form))
            flash("연락처가 등록되었습니다")
            # 저장 후에는 목록으로 이동한다 (새로고침해도 중복 저장되지 않게)
            return redirect(url_for("index"))

        return render_template("form.html", title="새 연락처", form={}, errors={})

    @app.route("/edit/<int:contact_id>", methods=["GET", "POST"])
    def edit(contact_id):
        # 없는 id면 404 화면을 보여 준다
        contact = db.get_contact(contact_id)
        if contact is None:
            abort(404)

        if request.method == "POST":
            form, errors = read_form()
            if errors:
                return render_template("form.html", title="연락처 수정",
                                       form=form, errors=errors)

            db.update_contact(contact_id, *to_db_values(form))
            flash("수정되었습니다")
            return redirect(url_for("index"))

        # GET: DB에 저장된 기존 값을 폼에 채워서 보여 준다
        return render_template("form.html", title="연락처 수정",
                               form=contact, errors={})

    # 삭제는 POST만 허용한다. 주소창에 입력하거나 링크로 접근(GET)하면 405 오류가 난다
    @app.route("/delete/<int:contact_id>", methods=["POST"])
    def delete(contact_id):
        if db.get_contact(contact_id) is None:
            abort(404)
        db.delete_contact(contact_id)
        flash("삭제되었습니다")
        return redirect(url_for("index"))

    @app.errorhandler(404)
    def not_found(e):
        # 없는 주소나 없는 연락처에 접근했을 때 보여 줄 화면
        return render_template("404.html"), 404

    return app


def read_form():
    """등록·수정 폼의 입력값을 읽어 validate()로 검사한다. (입력값, 오류)를 돌려준다."""
    # 앞뒤 공백을 지운다
    form = {key: request.form.get(key, "").strip()
            for key in ("name", "phone", "email", "address", "memo")}
    return form, validate(form)


# 전화번호: 숫자 2~3자리, 3~4자리, 4자리. 하이픈은 있어도 없어도 된다 (예: 010-1234-5678, 02-123-4567)
PHONE_RE = re.compile(r"^[0-9]{2,3}-?[0-9]{3,4}-?[0-9]{4}$")
# 이메일: 아이디@도메인.끝 (공백과 @가 두 번 들어가는 것은 허용하지 않는다)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_MAX = 30


def validate(form):
    """입력값을 검사해 {칸 이름: 오류 메시지} 사전을 돌려준다. 문제가 없으면 빈 사전."""
    errors = {}

    if not form["name"]:
        errors["name"] = "이름을 입력해 주세요."
    elif len(form["name"]) > NAME_MAX:
        errors["name"] = f"이름은 {NAME_MAX}자 이하로 입력해 주세요. (지금 {len(form['name'])}자)"

    if not form["phone"]:
        errors["phone"] = "전화번호를 입력해 주세요."
    elif not PHONE_RE.match(form["phone"]):
        errors["phone"] = "전화번호는 숫자와 하이픈(-)만 써서 010-1234-5678 형식으로 입력해 주세요."

    # 이메일은 선택 항목: 입력했을 때만 형식을 검사한다
    if form["email"] and not EMAIL_RE.match(form["email"]):
        errors["email"] = "이메일 형식이 올바르지 않습니다. 예) hong@example.com"

    return errors


def to_db_values(form):
    """DB 함수에 넘길 값 순서로 바꾼다. 비어 있는 선택 항목은 None(NULL)으로 저장한다."""
    return (
        form["name"],
        form["phone"],
        form["email"] or None,
        form["address"] or None,
        form["memo"] or None,
    )


# `python app.py`로 직접 실행할 때 debug 모드로 개발 서버를 켠다
if __name__ == "__main__":
    create_app().run(debug=True)
