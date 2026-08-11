"""
Day 6 - Outbound SIP Call Trigger (LiveKit + Linphone)

ShikshaMitra AI outbound learning call.

Flow:
1. Read Linphone destination.
2. Convert destination to the SIP user expected by LiveKit.
3. Dispatch ShikshaMitra agent to the outbound room.
4. Create a SIP participant using the configured outbound trunk.
5. Linphone app rings.
6. Learner answers and talks to ShikshaMitra AI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import time

from dotenv import load_dotenv
from livekit import api


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(".env.local")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("telephony.outbound.dial")


# ============================================================
# CONFIGURATION
# ============================================================

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

TRUNK_ID = (
    os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")
    or os.getenv("LIVEKIT_OUTBOUND_TRUNK_ID", "")
)

DEFAULT_SIP_URI = os.getenv(
    "LINPHONE_SIP_URI",
    "sip:shubham_sahu77@sip.linphone.org",
)

SIP_HOST = os.getenv(
    "SIP_OUTBOUND_HOST",
    "sip.linphone.org",
)

AGENT_NAME = os.getenv(
    "AGENT_NAME",
    "my-agent",
)


# ============================================================
# DESTINATION PARSER
# ============================================================

def extract_sip_user(raw_destination: str) -> str:
    """
    Convert different destination formats into the SIP user
    expected by LiveKit's sip_call_to parameter.

    Examples:

        shubham_sahu77
            -> shubham_sahu77

        sip:shubham_sahu77@sip.linphone.org
            -> shubham_sahu77

        shubham_sahu77@sip.linphone.org
            -> shubham_sahu77
    """

    destination = (raw_destination or "").strip()

    if not destination:
        destination = DEFAULT_SIP_URI.strip()

    # Remove sip: prefix
    if destination.lower().startswith("sip:"):
        destination = destination[4:]

    # Remove everything after @
    if "@" in destination:
        destination = destination.split("@", 1)[0]

    # Keep only a safe SIP user value
    destination = re.sub(r"\s+", "", destination)

    if not destination:
        raise ValueError(
            "Invalid SIP destination. Could not determine SIP username."
        )

    return destination


# ============================================================
# VALIDATION
# ============================================================

def validate_config() -> None:
    """Validate required LiveKit configuration."""

    missing = []

    if not LIVEKIT_URL:
        missing.append("LIVEKIT_URL")

    if not LIVEKIT_API_KEY:
        missing.append("LIVEKIT_API_KEY")

    if not LIVEKIT_API_SECRET:
        missing.append("LIVEKIT_API_SECRET")

    if not TRUNK_ID:
        missing.append("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# OUTBOUND CALL
# ============================================================

async def make_outbound_call(destination_arg: str) -> None:
    """Create an outbound SIP call to the Linphone user."""

    validate_config()

    # --------------------------------------------------------
    # Convert destination to LiveKit-compatible SIP user
    # --------------------------------------------------------

    sip_user = extract_sip_user(destination_arg)

    room_name = f"outbound-sip-{int(time.time())}"

    logger.info("=" * 70)
    logger.info("  ShikshaMitra AI - Day 6 Outbound SIP Call")
    logger.info("=" * 70)

    logger.info("  SIP User:       %s", sip_user)
    logger.info("  SIP Host:       %s", SIP_HOST)
    logger.info("  SIP URI:        sip:%s@%s", sip_user, SIP_HOST)
    logger.info("  LiveKit Room:   %s", room_name)
    logger.info("  SIP Trunk ID:   %s", TRUNK_ID)
    logger.info("  Agent Name:     %s", AGENT_NAME)

    logger.info("=" * 70)

    # --------------------------------------------------------
    # Connect to LiveKit
    # --------------------------------------------------------

    lkapi = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    try:

        # ====================================================
        # STEP 1 - DISPATCH AGENT
        # ====================================================

        logger.info("")
        logger.info(
            "[STEP 1] Dispatching ShikshaMitra AI to room '%s'...",
            room_name,
        )

        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name=AGENT_NAME,
            room=room_name,
            metadata=json.dumps(
                {
                    "outbound": True,
                    "sip_user": sip_user,
                    "phone_number": sip_user,
                    "purpose": "daily_learning_practice",
                }
            ),
        )

        dispatch = await lkapi.agent_dispatch.create_dispatch(
            dispatch_request
        )

        logger.info(
            "[OK] Agent dispatched successfully."
        )

        logger.info(
            "[OK] Dispatch ID: %s",
            dispatch.id,
        )

        # ====================================================
        # STEP 2 - CREATE SIP PARTICIPANT
        # ====================================================

        logger.info("")
        logger.info(
            "[STEP 2] Creating SIP participant..."
        )

        logger.info(
            "  Trunk: %s",
            TRUNK_ID,
        )

        logger.info(
            "  Destination user: %s",
            sip_user,
        )

        # IMPORTANT:
        #
        # LiveKit expects sip_call_to to be:
        #
        #     shubham_sahu77
        #
        # NOT:
        #
        #     sip:shubham_sahu77@sip.linphone.org
        #
        # because the trunk already knows the SIP provider/domain.

        sip_request = api.CreateSIPParticipantRequest(
            sip_trunk_id=TRUNK_ID,

            # IMPORTANT FIX
            sip_call_to=sip_user,

            room_name=room_name,

            participant_identity=f"learner-{sip_user}",

            participant_name="ShikshaMitra Learner",

            display_name="ShikshaMitra AI",

            wait_until_answered=True,

            play_dialtone=True,
        )

        logger.info(
            "[INFO] Sending SIP INVITE to LiveKit..."
        )

        sip_info = await lkapi.sip.create_sip_participant(
            sip_request
        )

        # ====================================================
        # SUCCESS
        # ====================================================

        logger.info("")
        logger.info("=" * 70)
        logger.info("  [SUCCESS] OUTBOUND CALL CREATED")
        logger.info("=" * 70)

        logger.info(
            "  Participant: %s",
            sip_info.participant_identity,
        )

        logger.info(
            "  SIP Call ID: %s",
            sip_info.sip_call_id,
        )

        logger.info(
            "  Room: %s",
            room_name,
        )

        logger.info("")
        logger.info(
            "  Your Linphone app should be ringing now."
        )

        logger.info(
            "  Answer the call to speak with ShikshaMitra AI."
        )

        logger.info("=" * 70)

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception as exc:

        logger.error("")
        logger.error("=" * 70)
        logger.error("  [FAILED] OUTBOUND SIP CALL")
        logger.error("=" * 70)

        logger.error(
            "  Error: %s",
            exc,
        )

        logger.error("")

        logger.error(
            "  Destination sent to LiveKit: %s",
            sip_user,
        )

        logger.error(
            "  Expected SIP URI: sip:%s@%s",
            sip_user,
            SIP_HOST,
        )

        logger.error(
            "  Trunk ID: %s",
            TRUNK_ID,
        )

        logger.error("=" * 70)

        logger.exception(
            "Full LiveKit error:"
        )

    finally:
        await lkapi.aclose()


# ============================================================
# COMMAND LINE
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "ShikshaMitra AI - "
            "Outbound SIP Dial Trigger"
        )
    )

    parser.add_argument(
        "--to",
        type=str,
        default=DEFAULT_SIP_URI,
        help=(
            "Linphone username or SIP URI. "
            "Example: shubham_sahu77 or "
            "sip:shubham_sahu77@sip.linphone.org"
        ),
    )

    args = parser.parse_args()

    asyncio.run(
        make_outbound_call(args.to)
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()