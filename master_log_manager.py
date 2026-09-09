import os

from sheet_manager import connect_sheets, get_or_create_worksheet


class MasterLogManager:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet
        configured_ids = os.getenv("MASTER_TEST_DISCORD_IDS", "")
        self.approved_ids = {
            value.strip() for value in configured_ids.split(",") if value.strip()
        }

    def log_if_approved(self, discord_id, display_name, values):
        if str(discord_id) not in self.approved_ids:
            return False
        worksheet = get_or_create_worksheet(self.spreadsheet, display_name)
        worksheet.append_row(values)
        return True


def create_master_log_manager(config, sheet_name):
    spreadsheet = connect_sheets(
        {"credentials_file": config["credentials_file"], "google_sheet_name": sheet_name}
    )
    return MasterLogManager(spreadsheet)
