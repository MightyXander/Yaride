"""
Smoke test для проверки, что модули черновиков Mini App экспортируют нужные функции.
Реальное E2E-тестирование sessionStorage требует browser environment (Playwright/Cypress).
"""


def test_search_wizard_functions_exist():
    """Проверка наличия функций для search wizard draft."""
    import sys
    from pathlib import Path

    # Добавляем miniapp/src/lib в path для импорта TypeScript модулей (через transpiler не получится,
    # но можем проверить, что файлы существуют и имеют ожидаемую структуру)
    miniapp_lib = Path(__file__).parent.parent / "miniapp" / "src" / "lib"
    search_wizard_file = miniapp_lib / "search-wizard.ts"
    create_wizard_file = miniapp_lib / "create-wizard.ts"

    assert search_wizard_file.exists(), "search-wizard.ts должен существовать"
    assert create_wizard_file.exists(), "create-wizard.ts должен существовать"

    # Проверяем, что в search-wizard.ts есть нужные экспорты
    search_wizard_content = search_wizard_file.read_text()
    assert "export function loadSearchWizardDraft" in search_wizard_content
    assert "export function saveSearchWizardDraft" in search_wizard_content
    assert "export function clearSearchWizardDraft" in search_wizard_content
    assert "export interface SearchWizardDraft" in search_wizard_content
    assert 'const KEY = "yaride.search.wizard.v1"' in search_wizard_content
    assert "sessionStorage" in search_wizard_content, "Должен использовать sessionStorage"

    # Проверяем, что create-wizard.ts уже существует с аналогичными функциями
    create_wizard_content = create_wizard_file.read_text()
    assert "export function loadCreateWizardDraft" in create_wizard_content
    assert "export function saveCreateWizardDraft" in create_wizard_content
    assert "export function clearCreateWizardDraft" in create_wizard_content
    assert "sessionStorage" in create_wizard_content


def test_search_tsx_uses_draft_persistence():
    """Проверка, что search.tsx импортирует и использует функции черновика."""
    from pathlib import Path

    search_tsx = Path(__file__).parent.parent / "miniapp" / "src" / "routes" / "search.tsx"
    assert search_tsx.exists(), "search.tsx должен существовать"

    content = search_tsx.read_text()
    assert 'from "@/lib/search-wizard"' in content, "Должен импортировать search-wizard"
    assert "loadSearchWizardDraft" in content, "Должен загружать черновик"
    assert "saveSearchWizardDraft" in content, "Должен сохранять черновик"
    assert "clearSearchWizardDraft" in content, "Должен очищать черновик при выходе"
    # Проверяем, что есть useEffect для автосохранения
    assert "useEffect" in content and "saveSearchWizardDraft(draft)" in content


def test_create_tsx_uses_draft_persistence():
    """Проверка, что create.tsx очищает черновик после успешной отправки."""
    from pathlib import Path

    create_tsx = Path(__file__).parent.parent / "miniapp" / "src" / "routes" / "create.tsx"
    assert create_tsx.exists(), "create.tsx должен существовать"

    content = create_tsx.read_text()
    assert 'from "@/lib/create-wizard"' in content, "Должен импортировать create-wizard"
    assert "clearCreateWizardDraft" in content, "Должен очищать черновик"
    # Проверяем, что очистка происходит в onSuccess
    assert "onSuccess" in content and content.count("clearCreateWizardDraft()") >= 2


def test_search_wizard_structure():
    """Проверка структуры SearchWizardDraft."""
    from pathlib import Path

    search_wizard_file = Path(__file__).parent.parent / "miniapp" / "src" / "lib" / "search-wizard.ts"
    content = search_wizard_file.read_text()

    # Проверяем обязательные поля черновика
    required_fields = [
        "phaseKind",
        "fromPointId",
        "fromLabel",
        "toPointId",
        "toLabel",
        "fromDistrict",
        "toDistrict",
        "pickDistrict",
        "date",
        "resultsMode",
        "departureTimeFilter",
        "minSeatsFreeFilter",
    ]

    for field in required_fields:
        assert f"{field}:" in content or f"{field}," in content, f"Поле {field} должно быть в SearchWizardDraft"
