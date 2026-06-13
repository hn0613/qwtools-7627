import copy
import streamlit as st
import nest_asyncio

from frontend.st_utils import get_backend_api_client
from frontend.utils import generate_random_name

nest_asyncio.apply()
backend_api_client = get_backend_api_client()


def generate_fork_version_id(original_id: str, all_configs: list) -> str:
    """
    Generate the next version ID when forking a config.
    Finds the highest existing version for the same base and increments it.
    """
    # Try to split original ID into base and version tag
    parts = original_id.rsplit("_", 1)
    if len(parts) == 2 and "." in parts[1]:
        config_base = parts[0]
    else:
        # No recognizable version tag — treat entire ID as base
        config_base = original_id

    # Find the highest existing version for this base
    max_tag = 0.0
    for config in all_configs:
        config_name = config.get("id", "")
        if not config_name:
            continue
        name_parts = config_name.rsplit("_", 1)
        if len(name_parts) == 2 and name_parts[0] == config_base:
            try:
                tag = float(name_parts[1])
                if tag > max_tag:
                    max_tag = tag
            except (ValueError, IndexError):
                continue

    # Generate next version
    if max_tag > 0:
        # Increment the minor version, preserving major
        tag_str = str(max_tag)
        if "." in tag_str:
            version_part, minor_part = tag_str.split(".")
            next_tag = f"{version_part}.{int(minor_part) + 1}"
        else:
            next_tag = f"{int(max_tag) + 1}.0"
    else:
        next_tag = "0.1"

    return f"{config_base}_{next_tag}"


def get_default_config_loader(controller_name: str):
    """
    Load default configuration for a controller with proper session state isolation.
    Uses controller-specific session state keys to prevent cross-contamination.
    Supports explicit Edit vs Fork mode when loading existing configs.
    """
    # Use controller-specific session state key to prevent cross-contamination
    config_key = f"config_{controller_name}"
    mode_key = f"config_editing_mode_{controller_name}"
    source_key = f"config_source_id_{controller_name}"

    try:
        all_configs = backend_api_client.controllers.list_controller_configs()
    except Exception as e:
        st.error(f"Failed to fetch controller configs: {e}")
        all_configs = []

    # Handle both old and new config format
    existing_configs = []
    for config in all_configs:
        config_name = config.get("id")
        if config_name:
            existing_configs.append(config_name.split("_")[0])

    # Create default configuration with unique ID
    default_dict = {
        "id": generate_random_name(existing_configs),
        "controller_name": controller_name
    }

    # Initialize controller-specific config if not exists
    if config_key not in st.session_state:
        st.session_state[config_key] = copy.deepcopy(default_dict)

    with st.expander("Configurations", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            use_default_config = st.checkbox(
                "Use default config",
                value=st.session_state.get(f"use_default_{controller_name}", True),
                key=f"use_default_{controller_name}"
            )
        with c2:
            if not use_default_config:
                # Filter configs by controller name
                configs = []
                for config in all_configs:
                    config_data = config.get("config", config)
                    if config_data.get("controller_name") == controller_name:
                        configs.append(config)

                if len(configs) > 0:
                    config_names = [config.get("id") for config in configs]
                    selected_config_name = st.selectbox(
                        "Select a config",
                        config_names,
                        key=f"config_select_{controller_name}"
                    )

                    # Mode selection: edit original or create new version
                    load_mode = st.radio(
                        "Load mode",
                        ["Edit original config", "Create new version"],
                        key=f"config_load_mode_{controller_name}",
                        horizontal=True
                    )

                    # Only reload config when the selection or mode actually changes.
                    # Without this guard, every Streamlit rerun (triggered by any
                    # widget interaction) would re-load the config from the backend,
                    # overwriting any parameter changes the user has made.
                    last_loaded_key = f"_last_loaded_{controller_name}"
                    current_selection = (selected_config_name, load_mode)
                    last_selection = st.session_state.get(last_loaded_key)

                    if current_selection != last_selection:
                        # Find the selected config
                        selected_config = None
                        for config in configs:
                            if config.get("id") == selected_config_name:
                                selected_config = config
                                break

                        if selected_config:
                            # Use deep copy to prevent shared references
                            config_data = selected_config.get("config", selected_config)
                            st.session_state[config_key] = copy.deepcopy(config_data)
                            st.session_state[config_key]["controller_name"] = controller_name

                            if load_mode == "Edit original config":
                                # Edit mode: keep original ID
                                st.session_state[config_key]["id"] = selected_config_name
                                st.session_state[mode_key] = "edit"
                                st.session_state[source_key] = selected_config_name
                            else:
                                # Fork mode: generate new version ID
                                new_id = generate_fork_version_id(
                                    selected_config_name, all_configs
                                )
                                st.session_state[config_key]["id"] = new_id
                                st.session_state[mode_key] = "new_version"
                                st.session_state[source_key] = selected_config_name

                        # Record what we just loaded so we skip on next rerun
                        st.session_state[last_loaded_key] = current_selection
                else:
                    st.warning("No existing configs found for this controller.")
                    # Clear mode state
                    st.session_state.pop(mode_key, None)
                    st.session_state.pop(source_key, None)
                    st.session_state.pop(f"_last_loaded_{controller_name}", None)
            else:
                # Using default config — clear mode/source state
                st.session_state.pop(mode_key, None)
                st.session_state.pop(source_key, None)
                st.session_state.pop(f"_last_loaded_{controller_name}", None)

    # Set legacy key for backward compatibility (but with deep copy)
    st.session_state["default_config"] = copy.deepcopy(st.session_state[config_key])


def get_controller_config(controller_name: str) -> dict:
    """
    Get the current configuration for a controller with proper isolation.
    Returns a deep copy to prevent shared reference mutations.
    """
    config_key = f"config_{controller_name}"

    if config_key not in st.session_state:
        # Initialize with basic config if not found
        existing_configs = []
        try:
            all_configs = backend_api_client.controllers.list_controller_configs()
            for config in all_configs:
                config_name = config.get("id")
                if config_name:
                    existing_configs.append(config_name.split("_")[0])
        except Exception:
            pass

        default_dict = {
            "id": generate_random_name(existing_configs),
            "controller_name": controller_name
        }
        st.session_state[config_key] = copy.deepcopy(default_dict)

    # Always return a deep copy to prevent mutations
    return copy.deepcopy(st.session_state[config_key])


def update_controller_config(controller_name: str, config_updates: dict) -> None:
    """
    Update the configuration for a controller with proper isolation.
    Performs a deep copy of the updates to prevent shared references.
    """
    config_key = f"config_{controller_name}"

    # Get current config or initialize if not exists
    current_config = get_controller_config(controller_name)

    # Deep copy the updates to prevent shared references
    safe_updates = copy.deepcopy(config_updates)

    # Update the config
    current_config.update(safe_updates)

    # Store the updated config
    st.session_state[config_key] = current_config

    # Update legacy key for backward compatibility
    st.session_state["default_config"] = copy.deepcopy(current_config)


def reset_controller_config(controller_name: str) -> None:
    """
    Reset the configuration for a controller, clearing all session state.
    """
    config_key = f"config_{controller_name}"
    loader_key = f"config_loader_initialized_{controller_name}"
    mode_key = f"config_editing_mode_{controller_name}"
    source_key = f"config_source_id_{controller_name}"

    # Clear controller-specific state
    st.session_state.pop(config_key, None)
    st.session_state.pop(loader_key, None)
    st.session_state.pop(mode_key, None)
    st.session_state.pop(source_key, None)

    # Clear related UI state
    st.session_state.pop(f"use_default_{controller_name}", None)
    st.session_state.pop(f"config_select_{controller_name}", None)
    st.session_state.pop(f"config_load_mode_{controller_name}", None)
    st.session_state.pop(f"_last_loaded_{controller_name}", None)

    # Clear legacy state if it matches this controller
    if st.session_state.get("default_config", {}).get("controller_name") == controller_name:
        st.session_state.pop("default_config", None)
