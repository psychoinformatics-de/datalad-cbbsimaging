from datalad import cfg

# If there's an alternative toolbox location configured,
# use it with the tests, too.
HIRNI_TOOLBOX_URL = \
    cfg.get("datalad.hirni.toolbox.url",
            "https://github.com/psychoinformatics-de/hirni-toolbox.git")
