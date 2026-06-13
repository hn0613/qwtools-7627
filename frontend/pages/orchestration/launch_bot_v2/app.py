import re
import time

import pandas as pd
import streamlit as st

from frontend.st_utils import get_backend_api_client, initialize_st_page

initialize_st_page(icon="🙌", show_readme=False)

# Initialize backend client
backend_api_client = get_backend_api_client()

# Initialize session state for persistent selections
if "selected_config_ids" not in st.session_state:
    st.session_state.selected_config_ids = set()


# ============================================================
# Helper Functions
# ============================================================

def get_controller_configs():
    """Get all controller configurations. Returns (list, error_message_or_None)."""
    try:
        configs = backend_api_client.controllers.list_controller_configs()
        return configs, None
    except Exception as e:
        return [], str(e)


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


def parse_controller_config(config):
    """Parse a single controller config into a normalized row dict.

    Compatible with both nested {id, config: {...}} and flat {id, controller_name, ...} formats.
    Returns (row_dict, None) on success or (None, warning_string) on failure.
    """
    if isinstance(config, str):
        return None, f"Unexpected config format (string): {config}"

    if not isinstance(config, dict):
        return None, f"Invalid config type: {type(config)}"

    config_name = config.get("id")
    if not config_name:
        return None, f"Config missing 'id' field: {config}"

    # Handle both nested and flat config format
    config_data = config.get("config", config)

    connector_name = config_data.get("connector_name", "Unknown")
    trading_pair = config_data.get("trading_pair", "Unknown")
    try:
        total_amount_quote = float(config_data.get("total_amount_quote", 0))
    except (ValueError, TypeError):
        total_amount_quote = 0.0

    controller_name = config_data.get("controller_name", config_name)
    controller_type = config_data.get("controller_type", "generic")

    # Split config base and version
    config_parts = config_name.split("_")
    if len(config_parts) > 1:
        version = config_parts[-1]
        config_base = "_".join(config_parts[:-1])
    else:
        config_base = config_name
        version = "N/A"

    return {
        "Config Base": config_base,
        "Version": version,
        "Controller Name": controller_name,
        "Controller Type": controller_type,
        "Connector": connector_name,
        "Trading Pair": trading_pair,
        "Total Amount (USDT)": total_amount_quote,
        "_config_name": config_name,
    }, None


def apply_filters(data, text, connector, controller_type):
    """Filter parsed config data by text search, connector, and controller type."""
    filtered = data

    if text:
        text_lower = text.lower()
        filtered = [
            row for row in filtered
            if text_lower in row["Config Base"].lower()
            or text_lower in row["Controller Name"].lower()
            or text_lower in row["Connector"].lower()
            or text_lower in row["Trading Pair"].lower()
        ]

    if connector and connector != "All":
        filtered = [row for row in filtered if row["Connector"] == connector]

    if controller_type and controller_type != "All":
        filtered = [row for row in filtered if row["Controller Type"] == controller_type]

    return filtered


def launch_new_bot(bot_name, image_name, credentials, selected_controllers, max_global_drawdown,
                   max_controller_drawdown):
    """Launch a new bot with the selected configuration."""
    start_time_str = time.strftime("%Y%m%d-%H%M")
    full_bot_name = f"{bot_name}-{start_time_str}"

    try:
        deploy_config = {
            "instance_name": full_bot_name,
            "credentials_profile": credentials,
            "controllers_config": selected_controllers,
            "image": image_name,
        }

        if max_global_drawdown is not None and max_global_drawdown > 0:
            deploy_config["max_global_drawdown_quote"] = max_global_drawdown
        if max_controller_drawdown is not None and max_controller_drawdown > 0:
            deploy_config["max_controller_drawdown_quote"] = max_controller_drawdown

        backend_api_client.bot_orchestration.deploy_v2_controllers(**deploy_config)
        st.success(f"Successfully deployed bot: {full_bot_name}")
        time.sleep(3)
        return True

    except Exception as e:
        st.error(f"Failed to deploy bot: {e}")
        return False


def delete_selected_configs(selected_controllers):
    """Delete selected controller configurations. Returns list of successfully deleted IDs."""
    deleted = []
    if not selected_controllers:
        st.warning("You need to select the controllers configs that you want to delete.")
        return deleted

    try:
        for config in selected_controllers:
            config_name = config.replace(".yml", "")
            backend_api_client.controllers.delete_controller_config(config_name)
            deleted.append(config)
            st.success(f"Deleted {config_name}")
        return deleted
    except Exception as e:
        st.error(f"Failed to delete configs: {e}")
        return deleted


# ============================================================
# Confirmation Dialogs
# ============================================================

@st.dialog("Confirm Deployment", width="large")
def confirm_deploy_dialog(bot_name, image_name, credentials, controller_details,
                          max_global_drawdown, max_controller_drawdown):
    """Show deployment confirmation dialog with full parameter summary."""
    start_time_str = time.strftime("%Y%m%d-%H%M")

    st.markdown("#### Bot Configuration")
    st.markdown(
        f"- **Instance Name:** `{bot_name}-{start_time_str}`\n"
        f"- **Credentials:** `{credentials}`\n"
        f"- **Image:** `{image_name}`"
    )

    if (max_global_drawdown and max_global_drawdown > 0) or \
       (max_controller_drawdown and max_controller_drawdown > 0):
        st.markdown("#### Risk Management")
        risk_lines = []
        if max_global_drawdown and max_global_drawdown > 0:
            risk_lines.append(f"- **Max Global Drawdown:** ${max_global_drawdown:,.2f} USDT")
        if max_controller_drawdown and max_controller_drawdown > 0:
            risk_lines.append(f"- **Max Controller Drawdown:** ${max_controller_drawdown:,.2f} USDT")
        st.markdown("\n".join(risk_lines))

    st.markdown(f"#### Controllers ({len(controller_details)})")
    summary_df = pd.DataFrame([
        {
            "Controller Name": d["Controller Name"],
            "Connector": d["Connector"],
            "Trading Pair": d["Trading Pair"],
            "Amount (USDT)": f"${d['Total Amount (USDT)']:,.2f}",
        }
        for d in controller_details
    ])
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    st.divider()
    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col_confirm:
        if st.button("✅ Confirm Deploy", type="primary", use_container_width=True):
            selected_ids = [d["_config_name"] for d in controller_details]
            with st.spinner("🚀 Starting Bot..."):
                if launch_new_bot(bot_name, image_name, credentials, selected_ids,
                                  max_global_drawdown, max_controller_drawdown):
                    st.rerun()


@st.dialog("Confirm Delete")
def confirm_delete_dialog(selected_controllers, controller_details):
    """Show delete confirmation dialog."""
    st.warning(
        f"⚠️ You are about to delete **{len(selected_controllers)}** controller configuration(s). "
        "This action cannot be undone."
    )

    names_df = pd.DataFrame([
        {"Config": d["Config Base"], "Version": d["Version"], "Controller": d["Controller Name"]}
        for d in controller_details
    ])
    st.dataframe(names_df, hide_index=True, use_container_width=True)

    st.divider()
    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col_confirm:
        if st.button("🗑️ Confirm Delete", type="primary", use_container_width=True):
            deleted = delete_selected_configs(selected_controllers)
            for config_id in deleted:
                st.session_state.selected_config_ids.discard(config_id)
            if deleted:
                time.sleep(1)
                st.rerun()


# ============================================================
# Page Layout
# ============================================================

st.title("🚀 Deploy Trading Bot")
st.subheader("Configure and deploy your automated trading strategy")

# Bot Configuration Section
with st.container(border=True):
    st.info("🤖 **Bot Configuration:** Set up your bot instance with basic configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        bot_name = st.text_input(
            "Instance Name",
            placeholder="Enter a unique name for your bot instance",
            key="bot_name_input"
        )

    with col2:
        try:
            available_credentials = backend_api_client.accounts.list_accounts()
            if available_credentials:
                credentials = st.selectbox(
                    "Credentials Profile",
                    options=available_credentials,
                    index=0,
                    key="credentials_select"
                )
            else:
                st.warning("No credential profiles found.")
                credentials = st.text_input(
                    "Credentials Profile",
                    value="master_account",
                    key="credentials_input"
                )
        except Exception as e:
            st.error(f"Failed to fetch credentials: {e}")
            credentials = st.text_input(
                "Credentials Profile",
                value="master_account",
                key="credentials_input"
            )

    with col3:
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
                key="image_select"
            )
        except Exception as e:
            st.error(f"Failed to fetch available images: {e}")
            image_name = st.text_input(
                "Hummingbot Image",
                value="hummingbot/hummingbot:latest",
                key="image_input"
            )

# Risk Management Section
with st.container(border=True):
    st.warning("⚠️ **Risk Management:** Set maximum drawdown limits in USDT to protect your capital")

    col1, col2 = st.columns(2)

    with col1:
        max_global_drawdown = st.number_input(
            "Max Global Drawdown (USDT)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            help="Maximum allowed drawdown across all controllers",
            key="global_drawdown_input"
        )

    with col2:
        max_controller_drawdown = st.number_input(
            "Max Controller Drawdown (USDT)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            help="Maximum allowed drawdown per controller",
            key="controller_drawdown_input"
        )

# Controllers Section
with st.container(border=True):
    st.success("🎛️ **Controller Selection:** Select the trading controllers you want to deploy with this bot instance")

    # Fetch configs
    all_controllers_config, fetch_error = get_controller_configs()

    if fetch_error:
        st.error(f"Failed to fetch controller configs: {fetch_error}")
        if st.button("🔄 Retry"):
            st.rerun()
    else:
        # Parse all configs
        all_data = []
        parse_warnings = []
        for config in all_controllers_config:
            parsed, warning = parse_controller_config(config)
            if parsed:
                all_data.append(parsed)
            elif warning:
                parse_warnings.append(warning)

        # Show parse warnings in collapsed expander
        if parse_warnings:
            with st.expander(f"⚠️ {len(parse_warnings)} config(s) could not be parsed", expanded=False):
                for w in parse_warnings:
                    st.caption(w)

        if not all_data:
            st.info("📭 No controller configurations available. Please create some configurations first.")
        else:
            # Prune stale IDs from session state (configs deleted externally)
            valid_ids = {d["_config_name"] for d in all_data}
            st.session_state.selected_config_ids &= valid_ids

            # --- Filter UI ---
            filter_text = st.text_input(
                "🔍 Search configs",
                placeholder="Search by config name, controller, connector, or trading pair...",
                key="filter_text_input"
            )

            # Build dropdown options from ALL data (not filtered)
            all_connectors = sorted({d["Connector"] for d in all_data if d["Connector"] != "Unknown"})
            all_controller_types = sorted({d["Controller Type"] for d in all_data if d["Controller Type"] != "generic"})

            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                filter_connector = st.selectbox(
                    "Connector",
                    options=["All"] + all_connectors,
                    key="filter_connector_select"
                )
            with fc2:
                filter_controller_type = st.selectbox(
                    "Controller Type",
                    options=["All"] + all_controller_types,
                    key="filter_controller_type_select"
                )
            with fc3:
                st.write("")
                st.write("")
                filters_active = bool(filter_text) or filter_connector != "All" or filter_controller_type != "All"
                if filters_active:
                    if st.button("Clear Filters", use_container_width=True):
                        st.session_state.filter_text_input = ""
                        st.session_state.filter_connector_select = "All"
                        st.session_state.filter_controller_type_select = "All"
                        st.rerun()

            # Apply filters
            filtered_data = apply_filters(all_data, filter_text, filter_connector, filter_controller_type)

            # Filter status line
            if filters_active:
                hidden_selected = len(
                    st.session_state.selected_config_ids - {d["_config_name"] for d in filtered_data}
                )
                status_parts = [f"Showing **{len(filtered_data)}** / **{len(all_data)}** configs"]
                if hidden_selected > 0:
                    status_parts.append(f"(**{hidden_selected}** selected configs hidden by filters)")
                st.caption(" · ".join(status_parts))

            if not filtered_data:
                st.info("No configs match the current filters.")
                if st.button("Clear Filters", key="clear_filters_empty"):
                    st.session_state.filter_text_input = ""
                    st.session_state.filter_connector_select = "All"
                    st.session_state.filter_controller_type_select = "All"
                    st.rerun()
            else:
                # Build DataFrame with selection state from session_state
                display_data = []
                for row in filtered_data:
                    display_data.append({
                        "Select": row["_config_name"] in st.session_state.selected_config_ids,
                        "Config Base": row["Config Base"],
                        "Version": row["Version"],
                        "Controller Name": row["Controller Name"],
                        "Controller Type": row["Controller Type"],
                        "Connector": row["Connector"],
                        "Trading Pair": row["Trading Pair"],
                        "Amount (USDT)": f"${row['Total Amount (USDT)']:,.2f}",
                        "_config_name": row["_config_name"],
                    })

                df = pd.DataFrame(display_data)

                edited_df = st.data_editor(
                    df,
                    column_config={
                        "Select": st.column_config.CheckboxColumn(
                            "Select",
                            help="Select controllers to deploy or delete",
                            default=False,
                        ),
                        "_config_name": None,
                    },
                    disabled=[col for col in df.columns if col != "Select"],
                    hide_index=True,
                    use_container_width=True,
                    key="controller_table"
                )

                # Sync checkbox state back to session_state (only for visible rows)
                for _, row in edited_df.iterrows():
                    config_id = row["_config_name"]
                    if row["Select"]:
                        st.session_state.selected_config_ids.add(config_id)
                    else:
                        st.session_state.selected_config_ids.discard(config_id)

                # Show selection count (includes selections hidden by filters)
                total_selected = len(st.session_state.selected_config_ids)
                if total_selected > 0:
                    st.success(f"✅ {total_selected} controller(s) selected")

                # Action buttons
                st.divider()
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🗑️ Delete Selected", type="secondary", use_container_width=True):
                        if st.session_state.selected_config_ids:
                            selected_ids = list(st.session_state.selected_config_ids)
                            details = [d for d in all_data
                                       if d["_config_name"] in st.session_state.selected_config_ids]
                            confirm_delete_dialog(selected_ids, details)
                        else:
                            st.warning("Please select at least one controller to delete.")

                with col2:
                    deploy_style = "primary" if st.session_state.selected_config_ids else "secondary"
                    if st.button("🚀 Deploy Bot", type=deploy_style, use_container_width=True):
                        if not bot_name:
                            st.warning("You need to define the bot name.")
                        elif not image_name:
                            st.warning("You need to select the hummingbot image.")
                        elif not st.session_state.selected_config_ids:
                            st.warning("Please select at least one controller to deploy.")
                        else:
                            details = [d for d in all_data
                                       if d["_config_name"] in st.session_state.selected_config_ids]
                            confirm_deploy_dialog(
                                bot_name, image_name, credentials, details,
                                max_global_drawdown, max_controller_drawdown
                            )
