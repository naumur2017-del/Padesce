def sample(_all_eligible, target_class_codes):
    eligible_target_apps = [
        app
        for app in _all_eligible
        if (
            str(getattr(getattr(app, "classe", None), "code", "") or "").strip()
            or str(getattr(app, "classe_label", "") or "").strip()
        )
        in target_class_codes
    ]
    return len(eligible_target_apps)
