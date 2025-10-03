# Sales Lead Tracker
# Version: v19.10.25
# Pioneer Broadband

API_KEY = "22179825a79dba61013e4fc3b9d30fa4"
FORM_ID = "252598168633065"

# --- User Authentication with Roles ---
# For a real application, use st.secrets for this information
USERS = {
    "Megan": {
        "name": "Megan",
        "password": "30mx,a&a",
        "role": "admin"
    },
    "Karter": {
        "name": "Karter",
        "password": "30mx,a&a",
        "role": "user"
    },
    "BJ": {
        "name": "Bj",
        "password": "30mx,a&a",
        "role": "admin"
    },
    "Gillian": {
        "name": "Gillian",
        "password": "30mx,a&a",
        "role": "user"
    },
    "Gabby": {
        "name": "Gabby",
        "password": "30mx,a&a",
        "role": "user"
    },
    "Billy": {
        "name": "Billy",
        "password": "30mx,a&a",
        "role": "user"
    }
}
# --------------------------------

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
    "assigned_to": 20, # <-- IMPORTANT: Replace 20 with your new Field ID
}

STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]
TEST_PREFIX = "TEST – Pioneer Broadband"
