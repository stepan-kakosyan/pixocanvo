from django.conf import settings


def language_switcher_options(request):
    options = []

    custom_options = getattr(settings, "LANGUAGE_SWITCHER_OPTIONS", None)
    source = custom_options if custom_options else getattr(settings, "LANGUAGES", [])

    for entry in source:
        if not entry or len(entry) < 2:
            continue

        code = str(entry[0])
        name = str(entry[1])
        raw_flag = str(entry[2]) if len(entry) > 2 else code.split("-")[0]
        flag = raw_flag.lower()

        options.append(
            {
                "code": code,
                "name": name,
                "flag": flag,
            }
        )

    current_code = str(getattr(request, "LANGUAGE_CODE", "")).lower()
    current_option = None
    visible_options = []
    for option in options:
        if option["code"].lower() == current_code:
            if current_option is None:
                current_option = option
            continue
        visible_options.append(option)

    if current_option is None and options:
        current_option = options[0]

    return {
        "LANGUAGE_SWITCHER_OPTIONS": options,
        "LANGUAGE_SWITCHER_CURRENT": current_option,
        "LANGUAGE_SWITCHER_VISIBLE_OPTIONS": visible_options,
    }
