try:
    from whitenoise.storage import CompressedManifestStaticFilesStorage
except Exception:  # pragma: no cover - settings only selects this when whitenoise exists.
    CompressedManifestStaticFilesStorage = None


class SafeCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
