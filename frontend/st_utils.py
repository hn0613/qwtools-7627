import inspect
import os.path
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from streamlit.commands.page_config import InitialSideBarState, Layout
from yaml import SafeLoader

from CONFIG import AUTH_SYSTEM_ENABLED
from frontend.pages.permissions import main_page, private_pages, public_pages


def initialize_st_page(title: Optional[str] = None, icon: str = "🤖", layout: Layout = 'wide',
                       initial_sidebar_state: InitialSideBarState = "expanded",
                       show_readme: bool = True):
    st.set_page_config(
        page_title=title,
        page_icon=icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar_state
    )

    # Add page title
    if title:
        st.title(title)

    # Get caller frame info safely
    frame: Optional[Union[inspect.FrameInfo, inspect.Traceback]] = None
    try:
        caller_frame = inspect.currentframe()
        if caller_frame is not None:
            caller_frame = caller_frame.f_back
            if caller_frame is not None:
                frame = inspect.getframeinfo(caller_frame)
    except Exception:
        pass

    if frame is not None and show_readme:
        current_directory = Path(os.path.dirname(frame.filename))
        readme_path = current_directory / "README.md"
        if readme_path.exists():
            with st.expander("About This Page"):
                st.write(readme_path.read_text())
        else:
            # Only show expander if README exists
            pass


def download_csv_button(df: pd.DataFrame, filename: str, key: str):
    csv = df.to_csv(index=False).encode('utf-8')
    return st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"{filename}.csv",
        mime="text/csv",
        key=key
    )


def style_metric_cards():
    # Removed custom metric styling to use default Streamlit styling
    pass


def get_backend_api_client():
    import atexit

    from hummingbot_api_client import SyncHummingbotAPIClient

    from CONFIG import BACKEND_API_HOST, BACKEND_API_PASSWORD, BACKEND_API_PORT, BACKEND_API_USERNAME

    # Use Streamlit session state to store singleton instance
    if 'backend_api_client' not in st.session_state or st.session_state.backend_api_client is None:
        try:
            # Create and enter the client context
            # Ensure URL has proper protocol
            if not BACKEND_API_HOST.startswith(('http://', 'https://')):
                base_url = f"http://{BACKEND_API_HOST}:{BACKEND_API_PORT}"
            else:
                base_url = f"{BACKEND_API_HOST}:{BACKEND_API_PORT}"

            client = SyncHummingbotAPIClient(
                base_url=base_url,
                username=BACKEND_API_USERNAME,
                password=BACKEND_API_PASSWORD
            )
            # Initialize the client using context manager
            client.__enter__()

            # Register cleanup function to properly exit the context manager
            def cleanup_client():
                try:
                    if 'backend_api_client' in st.session_state and st.session_state.backend_api_client is not None:
                        st.session_state.backend_api_client.__exit__(None, None, None)
                        st.session_state.backend_api_client = None
                except Exception:
                    pass  # Ignore cleanup errors

            # Register cleanup with atexit and session state
            atexit.register(cleanup_client)
            if 'cleanup_registered' not in st.session_state:
                st.session_state.cleanup_registered = True
                # Also register cleanup for session state changes
                st.session_state.backend_api_client_cleanup = cleanup_client

            # Check Docker after initialization
            if not client.docker.is_running():
                st.error("Docker is not running. Please make sure Docker is running.")
                cleanup_client()  # Clean up before stopping
                st.stop()

            st.session_state.backend_api_client = client
        except Exception as e:
            st.error(f"Failed to initialize API client: {str(e)}")
            st.stop()

    return st.session_state.backend_api_client


def _load_auth_config():
    """Load and validate authentication configuration from credentials.yml.

    Returns the parsed config dict, or None if the file is missing or malformed.
    Displays an error message in the Streamlit UI when loading fails.
    """
    credentials_path = Path('credentials.yml')
    if not credentials_path.exists():
        st.error(
            "Authentication is enabled but `credentials.yml` was not found. "
            "Please create the credentials file or disable authentication "
            "(set AUTH_SYSTEM_ENABLED=False)."
        )
        return None
    try:
        with open(credentials_path) as file:
            config = yaml.load(file, Loader=SafeLoader)
    except yaml.YAMLError as e:
        st.error(f"Failed to parse `credentials.yml`: {e}")
        return None

    # Validate required keys
    for key in ("credentials", "cookie"):
        if key not in config:
            st.error(f"`credentials.yml` is missing the required `{key}` section.")
            return None
    if "usernames" not in config["credentials"]:
        st.error("`credentials.yml` is missing `credentials.usernames`.")
        return None
    for cookie_key in ("name", "key", "expiry_days"):
        if cookie_key not in config["cookie"]:
            st.error(f"`credentials.yml` is missing `cookie.{cookie_key}`.")
            return None

    return config


def _get_authenticator(config):
    """Return the stauth.Authenticate instance, creating it once per session.

    The instance is cached in st.session_state so that it is reused across
    Streamlit reruns within the same session.  On a browser refresh the session
    state is wiped, so a fresh instance is created — this is expected and the
    cookie-based validation inside ``.login()`` will restore the auth state.
    """
    if "authenticator" not in st.session_state:
        st.session_state.authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days'],
        )
    return st.session_state.authenticator


def require_auth():
    """Guard function for private pages.

    Call this at the top of any page that should only be accessible to
    authenticated users.  When authentication is disabled (development / demo
    mode) the guard is a no-op.  When authentication is enabled and the user
    is not logged in, a warning is shown and the page execution is stopped via
    ``st.stop()``.
    """
    if not AUTH_SYSTEM_ENABLED:
        return

    if not st.session_state.get("authentication_status", False):
        st.warning("This page requires authentication. Please log in to access it.")
        st.stop()


def auth_system():
    """Determine which pages to expose based on authentication state.

    When ``AUTH_SYSTEM_ENABLED`` is False (the default) all pages — public and
    private — are returned so that the dashboard works without any login step
    during development and demos.

    When ``AUTH_SYSTEM_ENABLED`` is True the function:

    1. Loads ``credentials.yml`` (with error handling for missing / malformed
       files).
    2. Creates (or reuses) a ``stauth.Authenticate`` instance.
    3. Calls ``.login()`` which either validates the persistent cookie (on
       page refresh / new session) or renders the login form.
    4. Returns only public pages when the user is not authenticated, or all
       pages when authenticated.

    The cookie ``expiry_days`` in ``credentials.yml`` **must be > 0** so that
    the authentication cookie survives browser refreshes.  With
    ``expiry_days: 0`` the cookie is a session cookie and will typically be
    lost on refresh, forcing the user to log in again.
    """
    if not AUTH_SYSTEM_ENABLED:
        return {
            "Main": main_page(),
            **private_pages(),
            **public_pages(),
        }

    # --- Authentication enabled path ---

    config = _load_auth_config()
    if config is None:
        # credentials.yml is missing or broken — show only public pages so the
        # app stays usable, while the error message above explains the problem.
        return {
            "Main": main_page(),
            **public_pages(),
        }

    authenticator = _get_authenticator(config)

    # If we are already authenticated (either from a previous rerun in this
    # session, or because .login() below has already validated the cookie),
    # show the full page set.
    if st.session_state.get("authentication_status"):
        authenticator.logout(location="sidebar")
        st.sidebar.write(f'Welcome *{st.session_state["name"]}*')
        return {
            "Main": main_page(),
            **private_pages(),
            **public_pages(),
        }

    # Not yet authenticated in session state.  Call .login() which will:
    #   - Read the persistent cookie and validate the token → sets
    #     authentication_status to True if valid (e.g. after a browser
    #     refresh with a non-expired cookie).
    #   - If no valid cookie, render the login form widget.  On form
    #     submission with correct credentials, authentication_status becomes
    #     True; with wrong credentials it becomes False; before submission
    #     it stays None.
    authenticator.login()

    # Re-check after .login() — it may have validated the cookie.
    if st.session_state.get("authentication_status"):
        authenticator.logout(location="sidebar")
        st.sidebar.write(f'Welcome *{st.session_state["name"]}*')
        return {
            "Main": main_page(),
            **private_pages(),
            **public_pages(),
        }

    # Still not authenticated — show feedback and only public pages.
    if st.session_state.get("authentication_status") is False:
        st.error('Username/password is incorrect')
    # When authentication_status is None the login form is waiting for input;
    # no extra message needed.

    return {
        "Main": main_page(),
        **public_pages(),
    }
