v = env.ref("company_smart_theme.view_users_form_auth_signup_fixup", raise_if_not_found=False)
if not v:
    print("view not found")
else:
    new_arch = """
            <xpath expr="//header/button[@name='action_reset_password'][contains(@context, 'create_user')]" position="attributes">
                <attribute name="class">btn btn-primary</attribute>
                <attribute name="string">Send invitation email</attribute>
            </xpath>
            <xpath expr="//header/field[@name='state']" position="before">
                <button name="action_reset_password"
                        type="object"
                        string="Send password reset email"
                        class="btn btn-primary"
                        groups="base.group_erp_manager"
                        invisible="state != 'active' or id == uid"/>
            </xpath>
            <xpath expr="//div[@name='auth']/button[@name='action_reset_password']" position="attributes">
                <attribute name="class">btn btn-primary</attribute>
            </xpath>
"""
    v.write({"arch_db": new_arch})
    env.cr.commit()
    print("updated", v.id, "signup_url in arch:", "signup_url" in (v.arch_db or ""))
