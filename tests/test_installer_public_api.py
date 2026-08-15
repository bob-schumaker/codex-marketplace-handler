import inspect


def test_documented_public_api_is_available_from_package_root() -> None:
    from marketplace_installer import (
        ImportError,
        Marketplace,
        MarketplaceConflictError,
        ModificationConflictError,
        PluginEntry,
        PublishResult,
        PublisherError,
        UnmanagedPluginConflictError,
        import_marketplace,
        publish_embedded_marketplace,
        publish_marketplace,
    )

    assert callable(publish_marketplace)
    assert callable(publish_embedded_marketplace)
    assert callable(import_marketplace)
    assert all(
        isinstance(value, type)
        for value in (
            Marketplace,
            PluginEntry,
            PublishResult,
            PublisherError,
            MarketplaceConflictError,
            ModificationConflictError,
            UnmanagedPluginConflictError,
            ImportError,
        )
    )
    assert list(inspect.signature(publish_embedded_marketplace).parameters) == [
        "resource_package",
        "home",
        "dry_run",
        "force",
    ]
    assert list(inspect.signature(import_marketplace).parameters) == [
        "marketplace_root",
        "destination_resources",
        "selected_plugins",
        "expected_name",
    ]
