from datalad import cfg


def install_demo_dataset(ds, path, recursive=False):
    source = "https://github.com/psychoinformatics-de/hirni-demo"
    if "datalad.hirni.toolbox.url" in cfg:
        subds = ds.install(source=source,
                           path=path,
                           recursive=False)
        # overwrite tool-box url
        subds.repo.call_git(["config", "-f", ".gitmodules", "--replace-all",
                          "submodule.code/hirni-toolbox.url",
                          cfg.get("datalad.hirni.toolbox.url")])
        subds.save(".gitmodules", message="Rewrite toolbox URLfor hirni tests")
        ds.save(path, message="Rewrite toolbox URL for hirni tests")
        # resume recursion (if any)
        if recursive:
            for s in subds.subdatasets():
                subds.install(s['path'], recursive=True)
    else:
        ds.install(source=source, path=path, recursive=recursive)
