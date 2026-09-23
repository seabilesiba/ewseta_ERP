def post_init_hook(env):
    env["proc.cms.seed"].seed_all_websites()
