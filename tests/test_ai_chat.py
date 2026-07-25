from __future__ import annotations

import pytest

from offsetx_apollo_builder.outreach.ai_chat import AIChatService
from offsetx_apollo_builder.outreach.store import OutreachStore


@pytest.fixture()
def service(tmp_path):
    store = OutreachStore(tmp_path / "chat.db")
    store.initialize()
    yield AIChatService(store)
    store.close()


def test_schema_creates_ai_chat_tables(service):
    names = {
        row[0]
        for row in service.store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"ai_chats", "ai_chat_projects", "ai_messages"} <= names


def test_project_create_list_delete(service):
    assert service.list_projects() == []
    project = service.create_project("Carbon outreach")
    assert project["name"] == "Carbon outreach"
    assert len(service.list_projects()) == 1

    service.delete_project(project["id"])
    assert service.list_projects() == []


def test_project_name_is_required(service):
    with pytest.raises(ValueError):
        service.create_project("   ")


def test_chat_create_and_list(service):
    chat = service.create_chat("First chat")
    assert chat["title"] == "First chat"
    assert chat["project_id"] is None
    chats = service.list_chats()
    assert [c["id"] for c in chats] == [chat["id"]]


def test_chat_delete_removes_messages(service):
    chat = service.create_chat()
    service.add_message(chat["id"], "user", "hello")
    assert len(service.list_messages(chat["id"])) == 1

    service.delete_chat(chat["id"])
    assert service.list_chats() == []
    # cascade removed the messages too
    assert service.list_messages(chat["id"]) == []


def test_move_chat_into_and_out_of_project(service):
    project = service.create_project("Q3 pipeline")
    chat = service.create_chat("Lead research")

    moved = service.move_chat(chat["id"], project["id"])
    assert moved is not None and moved["project_id"] == project["id"]
    assert [c["id"] for c in service.list_chats(project_id=project["id"])] == [chat["id"]]

    removed = service.move_chat(chat["id"], None)
    assert removed is not None and removed["project_id"] is None


def test_deleting_project_keeps_its_chats(service):
    """ON DELETE SET NULL: chats must survive their project being deleted."""
    project = service.create_project("Temp project")
    chat = service.create_chat("Keep me", project["id"])

    service.delete_project(project["id"])

    surviving = service.get_chat(chat["id"])
    assert surviving is not None
    assert surviving["project_id"] is None


def test_rename_chat(service):
    chat = service.create_chat()
    renamed = service.rename_chat(chat["id"], "Renamed thread")
    assert renamed is not None and renamed["title"] == "Renamed thread"


def test_send_message_stores_both_turns_and_autotitles(service):
    chat = service.create_chat()  # default title "New chat"
    captured: dict[str, str] = {}

    def fake_provider(*, system_prompt: str, user_prompt: str) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "Here is a follow-up draft."

    reply = service.send_message(
        chat_id=chat["id"],
        user_content="Write a follow-up for a carbon credit prospect",
        provider_fn=fake_provider,
    )

    assert reply["role"] == "assistant"
    assert reply["content"] == "Here is a follow-up draft."

    messages = service.list_messages(chat["id"])
    assert [m["role"] for m in messages] == ["user", "assistant"]

    # the provider receives the conversation history, not just the last turn
    assert "carbon credit prospect" in captured["user"]
    assert "off_CRM" in captured["system"]

    # "New chat" is replaced by a title derived from the first message
    updated = service.get_chat(chat["id"])
    assert updated is not None and updated["title"] != "New chat"


def test_send_message_keeps_history_across_turns(service):
    chat = service.create_chat()
    prompts: list[str] = []

    def fake_provider(*, system_prompt: str, user_prompt: str) -> str:
        prompts.append(user_prompt)
        return f"reply {len(prompts)}"

    service.send_message(chat_id=chat["id"], user_content="first question", provider_fn=fake_provider)
    service.send_message(chat_id=chat["id"], user_content="second question", provider_fn=fake_provider)

    # second call must include the first exchange
    assert "first question" in prompts[1]
    assert "reply 1" in prompts[1]
    assert len(service.list_messages(chat["id"])) == 4


def test_send_message_rejects_empty_content(service):
    chat = service.create_chat()
    with pytest.raises(ValueError):
        service.send_message(
            chat_id=chat["id"], user_content="   ", provider_fn=lambda **_: "unused"
        )


def test_existing_v6_database_migrates_and_works(tmp_path):
    """A database created before the AI chat feature must gain the new tables."""
    db = tmp_path / "legacy.db"
    store = OutreachStore(db)
    store.initialize()
    store.connection.execute("PRAGMA user_version = 6")
    store.connection.execute("DROP TABLE IF EXISTS ai_chats")
    store.connection.execute("DROP TABLE IF EXISTS ai_messages")
    store.connection.execute("DROP TABLE IF EXISTS ai_chat_projects")
    store.connection.commit()
    store.close()

    reopened = OutreachStore(db)
    reopened.initialize()
    service = AIChatService(reopened)
    chat = service.create_chat("After migration")
    assert service.get_chat(chat["id"]) is not None
    reopened.close()
