import streamlit as st
import nest_asyncio

from frontend.st_utils import get_backend_api_client

nest_asyncio.apply()


def render_save_config(config_base_default: str, config_data: dict):
    st.write("### Upload Config to Hummingbot-API")
    backend_api_client = get_backend_api_client()
    try:
        all_configs = backend_api_client.controllers.list_controller_configs()
    except Exception as e:
        st.error(f"Failed to fetch controller configs: {e}")
        return

    # Determine editing mode from session state
    controller_name = config_data.get("controller_name", "")
    mode_key = f"config_editing_mode_{controller_name}"
    source_key = f"config_source_id_{controller_name}"
    is_edit = st.session_state.get(mode_key) == "edit"
    source_id = st.session_state.get(source_key, "")

    existing_config_id = config_data.get("id", "")

    if is_edit:
        # Edit mode: preserve the original config ID
        config_base = existing_config_id.rsplit("_", 1)[0] if "_" in existing_config_id else existing_config_id
        config_tag = existing_config_id.rsplit("_", 1)[1] if "_" in existing_config_id else "0.1"
    else:
        # New config / fork mode: auto-generate next version
        config_bases = set()
        for config in all_configs:
            config_name = config.get("id")
            if config_name:
                config_bases.add(config_name.rsplit("_", 1)[0])
        config_base = config_base_default.rsplit("_", 1)[0] if "_" in config_base_default else config_base_default
        if config_base in config_bases:
            config_tags = []
            for config in all_configs:
                config_name = config.get("id")
                if config_name:
                    name_parts = config_name.rsplit("_", 1)
                    if len(name_parts) == 2 and name_parts[0] == config_base:
                        try:
                            config_tags.append(float(name_parts[1]))
                        except (ValueError, IndexError):
                            continue
            if config_tags:
                max_tag = max(config_tags)
                tag_str = str(max_tag)
                if "." in tag_str:
                    version, tag = tag_str.split(".")
                    config_tag = f"{version}.{int(tag) + 1}"
                else:
                    config_tag = f"{int(max_tag) + 1}.0"
            else:
                config_tag = "0.1"
        else:
            config_tag = "0.1"

    # Show mode-specific status indicators
    if is_edit:
        st.info(f"Editing existing config: **{existing_config_id}**")
    elif source_id:
        st.info(f"Creating new version based on: **{source_id}**")

    # Config name / tag input fields
    c1, c2 = st.columns([1, 1])
    with c1:
        config_base = st.text_input("Config Base", value=config_base)
    with c2:
        config_tag = st.text_input("Config Tag", value=config_tag)

    # Compute the target config name
    config_name = f"{config_base}_{config_tag}"
    config_matches_existing = any(
        config.get("id") == config_name for config in all_configs
    )

    # Safety check: when not in edit mode and target already exists, require confirmation
    overwrite_confirmed = False
    confirm_key = f"confirm_overwrite_{controller_name}"
    if config_matches_existing and not is_edit:
        overwrite_confirmed = st.checkbox(
            f"I understand that '{config_name}' already exists and will be overwritten.",
            key=confirm_key
        )
        if not overwrite_confirmed:
            st.warning(
                f"Config '{config_name}' already exists. "
                "Check the box above to confirm overwrite."
            )

    # Upload/Update button
    button_label = "Update" if is_edit else "Upload"
    button_disabled = config_matches_existing and not is_edit and not overwrite_confirmed
    upload_config_to_backend = st.button(button_label, disabled=button_disabled)

    if upload_config_to_backend:
        config_data["id"] = config_name
        try:
            backend_api_client.controllers.create_or_update_controller_config(
                config_name=config_name,
                config=config_data
            )
            # Clear legacy session state
            st.session_state.pop("default_config", None)
            # Clear mode state
            st.session_state.pop(mode_key, None)
            st.session_state.pop(source_key, None)
            st.session_state.pop(confirm_key, None)

            # Mode-specific success message
            if is_edit:
                st.success(f"Updated existing config: **{config_name}**")
            elif source_id:
                st.success(
                    f"Created new config: **{config_name}** "
                    f"(based on: {source_id})"
                )
            else:
                st.success(f"Config uploaded successfully: **{config_name}**")
        except Exception as e:
            st.error(f"Failed to upload config: {e}")
