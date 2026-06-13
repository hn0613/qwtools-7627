import re
import time

import pandas as pd
import streamlit as st

from frontend.st_utils import get_backend_api_client, initialize_st_page

initialize_st_page(icon="🙌", show_readme=False)

# Initialize backend client
backend_api_client = get_backend_api_client()

# ---------------------------------------------------------------------------
# Session State Initialization (deploy_v2_ prefix to avoid cross-page collisions)
# ---------------------------------------------------------------------------
if "deploy_v2_selected_configs" not in st.session_state:
    st.session_state.deploy_v2_selected_configs = set()

if "deploy_v2_configs_cache" not in st.session_state:
    st.session_state.deploy_v2_configs_cache = None

if "deploy_v2_show_deploy_dialog" not in st.session_state:
    st.session_state.deploy_v2_show_deploy_dialog = False

if "deploy_v2_show_delete_dialog" not in st.session_state:
    st.session_state.deploy_v2_show_delete_dialog = False

if "deploy_v2_credentials_degraded" not in st.session_state:
    st.session_state.deploy_v2_credentials_degraded = False

if "deploy_v2_images_degraded" not in st.session_state:
    st.session_state.deploy_v2_images_degraded = False


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_controller_configs():
    """Get all controller configurations using the new API."""
    try:
        return backend_api_client.controllers.list_controller_configs()
    except Exception as e:
        st.error(f"Failed to fetch controller configs: {e}")
        return []


def filter_hummingbot_images(images):
    """Filter images to only show Hummingbot-related ones."""
    hummingbot_images = []
    pattern = r'.+/hummingbot:'

    for image in images:
        try:
            if re.match(pattern, image):
                hummingbot_images.append(image)
        except Exception:
            continue

    return hummingbot_images


def normalize_controller_configs(raw_configs):
    """
    Normalize controller configs from API into a consistent format.
    Handles both nested (new) and flat (old) API response formats.

    Returns:
        tuple: (normalized_list, warnings_list)
    """
    normalized = []
    warnings = []

    for config in raw_configs:
        if not isinstance(config, dict):
            warnings.append(
                f"Unexpected config format (expected dict, got {type(config).__name__}). Skipped."
            )
            continue

        config_id = config.get("id")
        if not config_id:
            warnings.append(f"Config missing 'id' field. Skipped: {str(config)[:80]}")
            continue

        # Handle dual format: nested vs flat
        config_data = config.get("config", config)

        if not isinstance(config_data, dict):
            warnings.append(f"Config '{config_id}' has non-dict data. Skipped.")
            continue

        connector_name = config_data.get("connector_name", "N/A")
        trading_pair = config_data.get("trading_pair", "N/A")
        try:
            total_amount_quote = float(config_data.get("total_amount_quote", 0))
        except (ValueError, TypeError):
            total_amount_quote = 0.0
            warnings.append(
                f"Config '{config_id}': invalid total_amount_quote, defaulted to 0."
            )

        controller_name = config_data.get("controller_name", config_id)
        controller_type = config_data.get("controller_type", "generic")

        # Split config_id into base + version using rsplit to handle names like
        # pmm_simple_v2_0.1 -> (pmm_simple_v2, 0.1) correctly
        parts = config_id.rsplit("_", 1)
        if len(parts) == 2 and parts[1] and parts[1][0].isdigit():
            config_base, version = parts[0], parts[1]
        else:
            config_base, version = config_id, "\u2014"

        normalized.append({
            "config_id": config_id,
            "config_base": config_base,
            "version": version,
            "controller_name": controller_name,
            "controller_type": controller_type,
            "connector_name": connector_name,
            "trading_pair": trading_pair,
            "total_amount_quote": total_amount_quote,
        })

    return normalized, warnings


def get_filter_options(configs):
    """Extract sorted unique values for filter dropdowns from normalized configs."""
    types = sorted({c["controller_type"] for c in configs if c["controller_type"]})
    connectors = sorted({
        c["connector_name"]
        for c in configs
        if c["connector_name"] and c["connector_name"] != "N/A"
    })
    pairs = sorted({
        c["trading_pair"]
        for c in configs
        if c["trading_pair"] and c["trading_pair"] != "N/A"
    })
    return types, connectors, pairs


def apply_filters(configs, text_filter="", type_filter=None,
                  connector_filter=None, pair_filter=None):
    """
    Filter normalized configs by text search and facet filters.
    All active filters are combined with AND logic.
    """
    result = configs
    text = (text_filter or "").strip().lower()

    if text:
        result = [
            c for c in result
            if text in c["config_id"].lower()
            or text in c["controller_name"].lower()
            or text in c["connector_name"].lower()
            or text in c["trading_pair"].lower()
        ]

    if type_filter:
        result = [c for c in result if c["controller_type"] in type_filter]

    if connector_filter:
        result = [c for c in result if c["connector_name"] in connector_filter]

    if pair_filter:
        result = [c for c in result if c["trading_pair"] in pair_filter]

    return result


def sync_selection_from_editor(edited_df, visible_ids):
    """
    Update session_state.deploy_v2_selected_configs based on data_editor output.

    For configs currently visible in the table, use the checkbox state from edited_df.
    For configs NOT visible (filtered out), preserve their existing selection state.
    This ensures filtering doesn't silently deselect hidden configs.
    """
    visible_set = set(visible_ids)

    visible_selected = set()
    for _, row in edited_df.iterrows():
        if row["Select"]:
            visible_selected.add(row["config_id"])

    # Preserve selection for configs not currently visible
    hidden_selected = st.session_state.deploy_v2_selected_configs - visible_set

    # Merge: visible selections from editor + hidden selections preserved
    st.session_state.deploy_v2_selected_configs = visible_selected | hidden_selected


# ---------------------------------------------------------------------------
# Core Actions
# ---------------------------------------------------------------------------

def launch_new_bot(bot_name, image_name, credentials, config_ids,
                   max_global_drawdown, max_controller_drawdown):
    """Launch a new bot with the selected configuration."""
    if not bot_name:
        st.warning("You need to define the bot name.")
        return False
    if not image_name:
        st.warning("You need to select the hummingbot image.")
        return False
    if not config_ids:
        st.warning("You need to select at least one controller config.")
        return False

    start_time_str = time.strftime("%Y%m%d-%H%M")
    full_bot_name = f"{bot_name}-{start_time_str}"

    try:
        deploy_config = {
            "instance_name": full_bot_name,
            "credentials_profile": credentials,
            "controllers_config": config_ids,
            "image": image_name,
        }

        if max_global_drawdown is not None and max_global_drawdown > 0:
            deploy_config["max_global_drawdown_quote"] = max_global_drawdown
        if max_controller_drawdown is not None and max_controller_drawdown > 0:
            deploy_config["max_controller_drawdown_quote"] = max_controller_drawdown

        backend_api_client.bot_orchestration.deploy_v2_controllers(**deploy_config)
        st.success(f"Successfully deployed bot: {full_bot_name}")
        return True

    except Exception as e:
        st.error(f"Failed to deploy bot: {e}")
        return False


def delete_selected_configs(selected_controllers):
    """Delete selected controller configurations."""
    if not selected_controllers:
        st.warning("You need to select the controllers configs that you want to delete.")
        return False

    success_count = 0
    for config in selected_controllers:
        config_name = config.replace(".yml", "")
        try:
            backend_api_client.controllers.delete_controller_config(config_name)
            st.success(f"Deleted {config_name}")
            success_count += 1
        except Exception as e:
            st.error(f"Failed to delete {config_name}: {e}")

    return success_count > 0


# ---------------------------------------------------------------------------
# Confirmation Dialogs
# ---------------------------------------------------------------------------

@st.dialog("Confirm Deployment", width="large")
def deploy_confirmation_dialog(bot_name, image_name, credentials,
                               selected_configs, max_global_dd, max_controller_dd):
    """Show deployment summary and ask for confirmation."""
    start_time_str = time.strftime("%Y%m%d-%H%M")
    full_bot_name = f"{bot_name}-{start_time_str}"

    st.markdown(f"**Instance Name:** `{full_bot_name}`")
    st.markdown(f"**Docker Image:** `{image_name}`")
    st.markdown(f"**Credentials Profile:** `{credentials}`")

    if st.session_state.get("deploy_v2_credentials_degraded"):
        st.warning(
            "Credentials were entered manually (API unavailable). "
            "Please double-check the profile name."
        )
    if st.session_state.get("deploy_v2_images_degraded"):
        st.warning(
            "Image was entered manually (API unavailable). "
            "Please double-check the image name."
        )

    if max_global_dd > 0 or max_controller_dd > 0:
        st.markdown("**Risk Limits:**")
        if max_global_dd > 0:
            st.markdown(f"- Max Global Drawdown: **${max_global_dd:,.2f}**")
        if max_controller_dd > 0:
            st.markdown(f"- Max Controller Drawdown: **${max_controller_dd:,.2f}**")
    else:
        st.warning("No drawdown limits set. The bot will run without drawdown protection.")

    st.markdown(f"**Controllers ({len(selected_configs)}):**")

    summary_data = [{
        "Controller": c["controller_name"],
        "Type": c["controller_type"],
        "Connector": c["connector_name"],
        "Pair": c["trading_pair"],
        "Amount": f"${c['total_amount_quote']:,.2f}",
    } for c in selected_configs]
    st.dataframe(
        pd.DataFrame(summary_data),
        hide_index=True,
        use_container_width=True,
    )

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Confirm Deploy", type="primary", use_container_width=True):
            config_ids = [c["config_id"] for c in selected_configs]
            with st.spinner("Deploying bot..."):
                success = launch_new_bot(
                    bot_name, image_name, credentials,
                    config_ids, max_global_dd, max_controller_dd,
                )
            st.session_state.deploy_v2_show_deploy_dialog = False
            if success:
                st.session_state.deploy_v2_selected_configs = set()
                st.session_state.deploy_v2_configs_cache = None
                st.rerun()

    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.deploy_v2_show_deploy_dialog = False
            st.rerun()


@st.dialog("Confirm Deletion")
def delete_confirmation_dialog(selected_config_ids):
    """Show list of configs to delete and ask for confirmation."""
    st.warning(
        "This action is irreversible. The following configurations "
        "will be permanently deleted:"
    )

    for cid in selected_config_ids:
        st.markdown(f"- `{cid}`")

    st.markdown(f"**Total: {len(selected_config_ids)} configuration(s)**")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Confirm Delete", type="primary", use_container_width=True):
            with st.spinner("Deleting configurations..."):
                success = delete_selected_configs(selected_config_ids)
            st.session_state.deploy_v2_show_delete_dialog = False
            if success:
                st.session_state.deploy_v2_selected_configs -= set(selected_config_ids)
                st.session_state.deploy_v2_configs_cache = None
                st.rerun()

    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.deploy_v2_show_delete_dialog = False
            st.rerun()


# ===========================================================================
# Page Body
# ===========================================================================

# Page Header
st.title("Deploy Trading Bot")
st.subheader("Configure and deploy your automated trading strategy")

# ---------------------------------------------------------------------------
# Bot Configuration Section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.info("**Bot Configuration:** Set up your bot instance with basic configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        bot_name = st.text_input(
            "Instance Name",
            placeholder="Enter a unique name for your bot instance",
            key="bot_name_input",
        )

    with col2:
        st.session_state.deploy_v2_credentials_degraded = False
        try:
            available_credentials = backend_api_client.accounts.list_accounts()
            if not available_credentials:
                st.warning("No credential profiles found.")
                credentials = st.text_input(
                    "Credentials Profile",
                    value="master_account",
                    key="credentials_input_fallback",
                )
            else:
                credentials = st.selectbox(
                    "Credentials Profile",
                    options=available_credentials,
                    index=0,
                    key="credentials_select",
                )
        except Exception as e:
            st.error(f"Failed to fetch credentials: {e}")
            st.session_state.deploy_v2_credentials_degraded = True
            credentials = st.text_input(
                "Credentials Profile",
                value="master_account",
                key="credentials_input",
            )

    with col3:
        st.session_state.deploy_v2_images_degraded = False
        try:
            all_images = backend_api_client.docker.get_available_images("hummingbot")
            available_images = filter_hummingbot_images(all_images)

            if not available_images:
                available_images = ["hummingbot/hummingbot:latest"]

            default_image = "hummingbot/hummingbot:latest"
            if default_image not in available_images:
                available_images.insert(0, default_image)

            image_name = st.selectbox(
                "Hummingbot Image",
                options=available_images,
                index=0,
                key="image_select",
            )
        except Exception as e:
            st.error(f"Failed to fetch available images: {e}")
            st.session_state.deploy_v2_images_degraded = True
            image_name = st.text_input(
                "Hummingbot Image",
                value="hummingbot/hummingbot:latest",
                key="image_input",
            )

# ---------------------------------------------------------------------------
# Risk Management Section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.warning(
        "**Risk Management:** Set maximum drawdown limits in USDT to protect your capital"
    )

    col1, col2 = st.columns(2)

    with col1:
        max_global_drawdown = st.number_input(
            "Max Global Drawdown (USDT)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            help="Maximum allowed drawdown across all controllers",
            key="global_drawdown_input",
        )

    with col2:
        max_controller_drawdown = st.number_input(
            "Max Controller Drawdown (USDT)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            help="Maximum allowed drawdown per controller",
            key="controller_drawdown_input",
        )

# ---------------------------------------------------------------------------
# Controllers Section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.success(
        "**Controller Selection:** Select the trading controllers "
        "you want to deploy with this bot instance"
    )

    # --- Fetch & Normalize Configs (with session state caching) ---
    if st.session_state.deploy_v2_configs_cache is None:
        raw_configs = get_controller_configs()
        normalized, norm_warnings = normalize_controller_configs(raw_configs)
        st.session_state.deploy_v2_configs_cache = normalized

        for w in norm_warnings:
            st.warning(w)

    all_configs = st.session_state.deploy_v2_configs_cache or []

    # --- Empty / Error State ---
    if not all_configs:
        st.warning(
            "No controller configurations available. "
            "Please create some configurations first."
        )
        if st.button("Retry", key="retry_configs"):
            st.session_state.deploy_v2_configs_cache = None
            st.rerun()
    else:
        # --- Filter Bar ---
        available_types, available_connectors, available_pairs = get_filter_options(
            all_configs
        )

        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(
            [2, 1.5, 1.5, 1.5]
        )

        with filter_col1:
            text_filter = st.text_input(
                "Search",
                placeholder="Search by name, controller, connector, pair...",
                key="deploy_filter_text",
            )

        with filter_col2:
            type_filter = st.multiselect(
                "Controller Type",
                options=available_types,
                default=[],
                key="deploy_filter_type",
            )

        with filter_col3:
            connector_filter = st.multiselect(
                "Connector",
                options=available_connectors,
                default=[],
                key="deploy_filter_connector",
            )

        with filter_col4:
            pair_filter = st.multiselect(
                "Trading Pair",
                options=available_pairs,
                default=[],
                key="deploy_filter_pair",
            )

        # Clear Filters + Refresh buttons
        any_filter_active = bool(
            text_filter or type_filter or connector_filter or pair_filter
        )
        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        with btn_col1:
            if any_filter_active:
                if st.button("Clear Filters", key="clear_filters"):
                    st.session_state.deploy_filter_text = ""
                    st.session_state.deploy_filter_type = []
                    st.session_state.deploy_filter_connector = []
                    st.session_state.deploy_filter_pair = []
                    st.rerun()
        with btn_col2:
            if st.button("Refresh", key="refresh_configs",
                         help="Reload configs from API"):
                st.session_state.deploy_v2_configs_cache = None
                st.rerun()

        # Apply filters
        filtered_configs = apply_filters(
            all_configs, text_filter, type_filter, connector_filter, pair_filter
        )

        # --- No filter results ---
        if not filtered_configs:
            st.info(
                f"No configs match your filters. "
                f"({len(all_configs)} total configs available)"
            )
        else:
            # --- Build DataFrame with selection from session state ---
            selected = st.session_state.deploy_v2_selected_configs
            rows = []
            for c in filtered_configs:
                rows.append({
                    "Select": c["config_id"] in selected,
                    "config_id": c["config_id"],
                    "Config Base": c["config_base"],
                    "Version": c["version"],
                    "Controller Name": c["controller_name"],
                    "Controller Type": c["controller_type"],
                    "Connector": c["connector_name"],
                    "Trading Pair": c["trading_pair"],
                    "Amount (USDT)": f"${c['total_amount_quote']:,.2f}",
                })

            df = pd.DataFrame(rows)
            visible_ids = [c["config_id"] for c in filtered_configs]

            edited_df = st.data_editor(
                df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select controllers to deploy or delete",
                        default=False,
                    ),
                    "config_id": None,  # Hide this column
                },
                disabled=[col for col in df.columns if col != "Select"],
                hide_index=True,
                use_container_width=True,
                key="controller_table",
            )

            # Sync editor state back to session state
            sync_selection_from_editor(edited_df, visible_ids)

            # Display selection summary
            current_selection = st.session_state.deploy_v2_selected_configs
            if current_selection:
                total_selected = len(current_selection)
                visible_selected = len(current_selection & set(visible_ids))
                hidden_selected = total_selected - visible_selected

                msg = f"{total_selected} controller(s) selected for deployment"
                if hidden_selected > 0:
                    msg += f" ({hidden_selected} hidden by filters)"
                st.success(msg)

            # --- Action Buttons ---
            st.divider()
            col1, col2 = st.columns(2)

            with col1:
                if st.button(
                    f"Delete Selected ({len(current_selection)})",
                    type="secondary",
                    use_container_width=True,
                    disabled=len(current_selection) == 0,
                ):
                    st.session_state.deploy_v2_show_delete_dialog = True

            with col2:
                deploy_type = "primary" if current_selection else "secondary"
                if st.button(
                    f"Deploy Bot ({len(current_selection)})",
                    type=deploy_type,
                    use_container_width=True,
                    disabled=len(current_selection) == 0,
                ):
                    if not bot_name:
                        st.warning("Please enter a bot instance name.")
                    elif not image_name:
                        st.warning("Please select a Hummingbot image.")
                    elif not credentials:
                        st.warning("Please select a credentials profile.")
                    else:
                        st.session_state.deploy_v2_show_deploy_dialog = True

# ---------------------------------------------------------------------------
# Dialog Rendering (outside container to avoid nesting issues)
# ---------------------------------------------------------------------------
if st.session_state.deploy_v2_show_deploy_dialog:
    selected_full_configs = [
        c
        for c in (st.session_state.deploy_v2_configs_cache or [])
        if c["config_id"] in st.session_state.deploy_v2_selected_configs
    ]
    deploy_confirmation_dialog(
        bot_name=bot_name,
        image_name=image_name,
        credentials=credentials,
        selected_configs=selected_full_configs,
        max_global_dd=max_global_drawdown,
        max_controller_dd=max_controller_drawdown,
    )

if st.session_state.deploy_v2_show_delete_dialog:
    delete_confirmation_dialog(
        selected_config_ids=sorted(st.session_state.deploy_v2_selected_configs)
    )
