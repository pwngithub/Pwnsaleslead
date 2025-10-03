# Sales Lead Tracker
# Version: v19.10.25
# Pioneer Broadband

# All sensitive data has been moved to .streamlit/secrets.toml

FIELD_ID = {
    "name_first": "first_3",
    "name_last": "last_3",
    "source": 4,
    "status": 6,
    "notes": 10,
    "lost_reason": 17,
    "service_type": 18,
    "address": 19,
    "survey_scheduled_date": 12,
    "survey_completed_date": 13,
    "scheduled_date": 14,
    "installed_date": 15,
    "waiting_on_customer_date": 16,
    "assigned_to": 20,
    "next_action_date": 21,
    "next_action": 22,
}

STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]
TEST_PREFIX = "TEST – Pioneer Broadband"
