import streamlit as st

from frontend.components.credentials_utils import (
    fetch_accounts_data,
    safe_add_credential,
    safe_create_account,
    safe_delete_account,
    safe_delete_credential,
)
from frontend.st_utils import get_backend_api_client, initialize_st_page

initialize_st_page(title="Credentials", icon="🔑")

# Page content
client = get_backend_api_client()
NUM_COLUMNS = 4


# ---------------------------------------------------------------------------
# Cached connector config map — avoids re-fetching on every full-page rerun
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_all_connectors_config_map():
    connectors = client.connectors.list_connectors()
    config_map_dict = {}
    for connector_name in connectors:
        try:
            config_map = client.connectors.get_config_map(connector_name=connector_name)
            config_map_dict[connector_name] = config_map
        except Exception:
            config_map_dict[connector_name] = []
    return config_map_dict


all_connector_config_map = get_all_connectors_config_map()


# ---------------------------------------------------------------------------
# Shared state: fetch once per full-page load, re-fetch after mutations
# ---------------------------------------------------------------------------
def _refresh_state():
    accounts, credentials = fetch_accounts_data(client)
    st.session_state.cred_accounts = accounts
    st.session_state.cred_credentials = credentials


if "cred_accounts" not in st.session_state or st.session_state.get("cred_needs_refresh", True):
    _refresh_state()
    st.session_state.cred_needs_refresh = False


# ---------------------------------------------------------------------------
# Fragment 1 — Account list + management actions
# ---------------------------------------------------------------------------
@st.fragment
def accounts_section():
    accounts = st.session_state.cred_accounts
    credentials = st.session_state.cred_credentials

    # --- Display accounts and their credentials ---
    if accounts:
        n_accounts = len(accounts)
        for i in range(0, n_accounts, NUM_COLUMNS):
            cols = st.columns(NUM_COLUMNS)
            for j, account in enumerate(accounts[i:i + NUM_COLUMNS]):
                with cols[j]:
                    st.subheader(f"\U0001f3e6  {account}")
                    cred_entries = credentials.get(account, [])
                    if cred_entries:
                        for entry in cred_entries:
                            st.caption(f"\U0001f511 {entry.display_name}")
                    else:
                        st.caption("暂无凭证")
    else:
        st.info("暂无账号，可在下方创建。")

    st.markdown("---")

    # --- Create / Delete Account / Delete Credential ---
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.header("创建账号")
        new_name = st.text_input("账号名称", key="new_account_input")
        if st.button("创建账号", key="btn_create_account"):
            ok, msg = safe_create_account(client, new_name, accounts)
            if ok:
                st.success(msg)
                st.session_state.cred_needs_refresh = True
                st.rerun()  # Full-page rerun to sync both fragments
            else:
                st.error(msg)

    with c2:
        st.header("删除账号")
        del_options = accounts if accounts else ["—"]
        del_account = st.selectbox("选择账号", options=del_options, key="del_account_select")
        if st.button("删除账号", key="btn_delete_account"):
            ok, msg = safe_delete_account(client, del_account)
            if ok:
                st.warning(msg)
                st.session_state.cred_needs_refresh = True
                st.rerun()
            else:
                st.error(msg)

    with c3:
        st.header("删除凭证")
        del_cred_account = st.selectbox(
            "选择账号", options=del_options, key="del_cred_account_select"
        )
        cred_entries = credentials.get(del_cred_account, [])
        cred_options = [e.display_name for e in cred_entries] if cred_entries else ["—"]
        del_cred_display = st.selectbox(
            "选择凭证", options=cred_options, key="del_cred_select"
        )
        if st.button("删除凭证", key="btn_delete_credential"):
            # Find the matching entry to get the correct delete_identifier
            matching = [e for e in cred_entries if e.display_name == del_cred_display]
            if matching:
                ok, msg = safe_delete_credential(
                    client, del_cred_account, matching[0].delete_identifier
                )
                if ok:
                    st.warning(msg)
                    st.session_state.cred_needs_refresh = True
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("未找到对应凭证，请确认选择。")


accounts_section()

st.markdown("---")


# ---------------------------------------------------------------------------
# Fragment 2 — Add credentials
# ---------------------------------------------------------------------------
@st.fragment
def add_credentials_section():
    accounts = st.session_state.cred_accounts

    st.header("添加凭证")
    c1, c2 = st.columns([1, 1])
    with c1:
        account_options = accounts if accounts else ["—"]
        account_name = st.selectbox("选择账号", options=account_options, key="add_cred_account")
    with c2:
        all_connectors = list(all_connector_config_map.keys())
        binance_perpetual_index = (
            all_connectors.index("binance_perpetual")
            if "binance_perpetual" in all_connectors
            else 0
        )
        connector_name = st.selectbox(
            "选择连接器", options=all_connectors,
            index=binance_perpetual_index, key="add_cred_connector",
        )
        config_map = all_connector_config_map.get(connector_name, [])

    st.write(f"**{connector_name}** 的配置字段:")
    config_inputs = {}

    # Custom logic for XRPL connector (preserved)
    if connector_name == "xrpl":
        xrpl_fields = {
            "xrpl_secret_key": "",
            "wss_node_urls": "wss://xrplcluster.com,wss://s1.ripple.com,wss://s2.ripple.com",
        }
        for field, default_value in xrpl_fields.items():
            if field == "xrpl_secret_key":
                config_inputs[field] = st.text_input(
                    field, type="password", key=f"xrpl_{field}"
                )
            else:
                config_inputs[field] = st.text_input(
                    field, value=default_value, key=f"xrpl_{field}"
                )

        if st.button("提交凭证", key="submit_xrpl"):
            ok, msg = safe_add_credential(client, account_name, connector_name, config_inputs)
            if ok:
                st.success(f"\u2705 {msg}")
                st.session_state.cred_needs_refresh = True
                st.rerun()  # Full-page rerun — accounts section will update too
            else:
                st.error(msg)
    else:
        cols = st.columns(NUM_COLUMNS)
        for i, config in enumerate(config_map):
            with cols[i % (NUM_COLUMNS - 1)]:
                config_inputs[config] = st.text_input(
                    config, type="password", key=f"{connector_name}_{config}"
                )

        with cols[-1]:
            if st.button("提交凭证", key="submit_generic"):
                ok, msg = safe_add_credential(
                    client, account_name, connector_name, config_inputs
                )
                if ok:
                    st.success(f"\u2705 {msg}")
                    st.session_state.cred_needs_refresh = True
                    st.rerun()
                else:
                    st.error(msg)


add_credentials_section()
