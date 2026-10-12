def post_init_hook(env):
    env["proc.cms.seed"].seed_all_websites()
    env["proc.cms.seed"].apply_nav_layout()
