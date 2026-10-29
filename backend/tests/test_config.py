from app.config import Settings


def test_local_project_overrides_inherited_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "old-shell-project")
    monkeypatch.setenv("GEMINI_MODEL", "inherited-model")
    config = tmp_path / ".env"
    config.write_text("GOOGLE_CLOUD_PROJECT=new-local-project\n")
    settings = Settings(_env_file=config)
    assert settings.google_cloud_project == "new-local-project"
    assert settings.gemini_model == "inherited-model"


def test_deployment_uses_environment_without_local_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "deployment-project")
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert settings.google_cloud_project == "deployment-project"
