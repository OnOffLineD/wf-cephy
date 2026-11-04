import os
import shutil
import tempfile

# Set before any app module loads: tests must not touch the user's data or open real windows.
_user_data_dir = tempfile.mkdtemp(prefix="wf_test_userdata_")
os.environ["WF_USER_DATA_DIR"] = _user_data_dir
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_user_data_dir, ignore_errors=True)
