import nest_asyncio
import streamlit as st

from frontend.st_utils import get_backend_api_client, initialize_st_page

nest_asyncio.apply()

initialize_st_page(title="Credentials", icon="🔑")


# --- Helper functions ---

def _safe_rerun():
    """Fragment-scoped rerun with fallback."""
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()


def _show_feedback():
    """Display and clear stored feedback message after rerun."""
    feedback = st.session_state.pop("_cred_feedback", None)
    if feedback:
        getattr(st, feedback["type"])(feedback["msg"])


def _parse_connector_names(credentials_data):
    """Parse varying credential formats into deduplicated sorted connector name list."""
    if isinstance(credentials_data, list):
        if credentials_data and isinstance(credentials_data[0], str):
            return sorted(set(c.split(".")[0] for c in credentials_data))
        elif credentials_data and isinstance(credentials_data[0], dict):
            return sorted(set(
                cred.get('connector', cred.get('connector_name', ''))
                for cred in credentials_data
                if cred.get('connector') or cred.get('connector_name')
            ))
        return []
    elif isinstance(credentials_data, dict):
        return sorted(credentials_data.keys())
    return []


# --- Page content ---

client = get_backend_api_client()
NUM_COLUMNS = 4


def get_all_connectors_config_map():
    connectors = client.connectors.list_connectors()
    config_map_dict = {}
    for connector_name in connectors:
        try:
            config_map = client.connectors.get_config_map(connector_name=connector_name)
            config_map_dict[connector_name] = config_map
        except Exception as e:
            st.warning(f"Could not get config map for {connector_name}: {e}")
            config_map_dict[connector_name] = []
    return config_map_dict


if "connector_config_map" not in st.session_state:
    st.session_state["connector_config_map"] = get_all_connectors_config_map()
all_connector_config_map = st.session_state["connector_config_map"]


@st.fragment
def accounts_section():
    _show_feedback()

    # Get fresh accounts list
    accounts = client.accounts.list_accounts()
    st.session_state["credentials_accounts"] = accounts

    if accounts:
        n_accounts = len(accounts)
        # Ensure master_account is first
        if "master_account" in accounts:
            accounts.remove("master_account")
            accounts.insert(0, "master_account")
        for i in range(0, n_accounts, NUM_COLUMNS):
            cols = st.columns(NUM_COLUMNS)
            for j, account in enumerate(accounts[i:i + NUM_COLUMNS]):
                with cols[j]:
                    st.subheader(f"🏦  {account}")
                    credentials = client.accounts.list_account_credentials(account)
                    connector_names = _parse_connector_names(credentials)
                    if connector_names:
                        for name in connector_names:
                            st.markdown(f"- `{name}`")
                    else:
                        st.caption("No credentials")
    else:
        st.write("No accounts available.")

    st.markdown("---")

    # Account management actions
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.header("Create a New Account")
        new_account_name = st.text_input("New Account Name")
        if st.button("Create Account"):
            sanitized = new_account_name.strip().replace(" ", "_").strip("_")
            if not sanitized:
                st.warning("Please enter an account name.")
                st.stop()
            if not all(c.isalnum() or c == "_" for c in sanitized):
                st.warning("Account name can only contain letters, numbers, and underscores.")
                st.stop()
            if sanitized in accounts:
                st.warning(f"Account '{sanitized}' already exists.")
                st.stop()
            response = client.accounts.add_account(sanitized)
            st.session_state["_cred_feedback"] = {
                "type": "success",
                "msg": f"Account '{sanitized}' created successfully."
            }
            _safe_rerun()

    with c2:
        st.header("Delete an Account")
        delete_account_name = st.selectbox("Select Account to Delete",
                                           options=accounts if accounts else ["No accounts available"])
        if st.button("Delete Account"):
            if delete_account_name and delete_account_name != "No accounts available":
                response = client.accounts.delete_account(delete_account_name)
                st.session_state["_cred_feedback"] = {
                    "type": "success",
                    "msg": f"Account '{delete_account_name}' deleted."
                }
                _safe_rerun()
            else:
                st.warning("Please select a valid account.")

    with c3:
        st.header("Delete Credential")
        delete_account_cred_name = st.selectbox("Select the credentials account",
                                                options=accounts if accounts else ["No accounts available"])
        credentials_data = client.accounts.list_account_credentials(delete_account_cred_name)
        creds_for_account = _parse_connector_names(credentials_data)
        delete_cred_name = st.selectbox("Select a Credential to Delete",
                                        options=creds_for_account if creds_for_account else [
                                            "No credentials available"])
        if st.button("Delete Credential"):
            if (delete_account_cred_name and delete_account_cred_name != "No accounts available") and \
                    (delete_cred_name and delete_cred_name != "No credentials available"):
                response = client.accounts.delete_credential(delete_account_cred_name, delete_cred_name)
                st.session_state["_cred_feedback"] = {
                    "type": "success",
                    "msg": f"Credential '{delete_cred_name}' removed from '{delete_account_cred_name}'."
                }
                _safe_rerun()
            else:
                st.warning("Please select a valid account and credential.")


accounts_section()

st.markdown("---")


# Section to add credentials
@st.fragment
def add_credentials_section():
    st.header("Add Credentials")
    accounts = st.session_state.get("credentials_accounts", [])

    c1, c2 = st.columns([1, 1])
    with c1:
        account_name = st.selectbox("Select Account", options=accounts if accounts else ["No accounts available"])
    with c2:
        all_connectors = list(all_connector_config_map.keys())
        binance_perpetual_index = all_connectors.index(
            "binance_perpetual") if "binance_perpetual" in all_connectors else None
        connector_name = st.selectbox("Select Connector", options=all_connectors, index=binance_perpetual_index)
        config_map = all_connector_config_map.get(connector_name, [])

    st.write(f"Configuration Map for {connector_name}:")
    config_inputs = {}

    # Custom logic for XRPL connector
    if connector_name == "xrpl":
        xrpl_fields = {
            "xrpl_secret_key": "",
            "wss_node_urls": "wss://xrplcluster.com,wss://s1.ripple.com,wss://s2.ripple.com",
        }
        for field, default_value in xrpl_fields.items():
            if field == "xrpl_secret_key":
                config_inputs[field] = st.text_input(field, type="password", key=f"{connector_name}_{field}")
            else:
                config_inputs[field] = st.text_input(field, value=default_value, key=f"{connector_name}_{field}")
    else:
        # Default behavior for other connectors
        cols = st.columns(NUM_COLUMNS)
        for i, config in enumerate(config_map):
            with cols[i % (NUM_COLUMNS - 1)]:
                config_inputs[config] = st.text_input(config, type="password", key=f"{connector_name}_{config}")

    # Unified submit logic for all connectors
    if st.button("Submit Credentials"):
        empty_fields = [k for k, v in config_inputs.items() if not v.strip()]
        if empty_fields:
            st.error(f"Please fill in: {', '.join(empty_fields)}")
            st.stop()
        response = client.accounts.add_credential(account_name, connector_name, config_inputs)
        if response:
            st.session_state["_cred_feedback"] = {
                "type": "success",
                "msg": f"Successfully added {connector_name} to {account_name}!"
            }
            _safe_rerun()
        else:
            st.error(f"Failed to add credentials for {connector_name}.")


add_credentials_section()
