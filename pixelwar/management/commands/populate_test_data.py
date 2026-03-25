"""
Management command to populate test data with realistic users and activities.
Loads pre-defined pixels from global-canvas-prepropulate.json, distributes
them across all test users, and saves everything to the database.
"""

import json
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from pixelwar.models import (
    Community,
    CommunityMembership,
    Pixel,
    UserAction,
)

CANVAS_JSON = Path(settings.BASE_DIR) / "global-canvas-prepropulate.json"


# Realistic user data from different countries
USERS_DATA = [
    # Japanese
    ("tanaka_yuki", "Tanaka Yuki", "tanaka.yuki@gmail.jp"),
    ("yamamoto_akira", "Yamamoto Akira", "yamamoto.akira@gmail.jp"),
    # Spanish
    ("garcia_miguel", "García Miguel", "garcia.miguel@gmail.es"),
    ("martinez_lucia", "Martínez Lucía", "martinez.lucia@gmail.es"),
    # French
    ("martin_pierre", "Martin Pierre", "martin.pierre@gmail.fr"),
    ("bernard_isabelle", "Bernard Isabelle", "bernard.isabelle@gmail.fr"),
    # German
    ("mueller_hans", "Müller Hans", "mueller.hans@web.de"),
    ("schmidt_katie", "Schmidt Katie", "schmidt.katie@web.de"),
    # Italian
    ("rossi_marco", "Rossi Marco", "rossi.marco@gmail.it"),
    ("bianchi_giulia", "Bianchi Giulia", "bianchi.giulia@gmail.it"),
    # Russian
    ("ivanov_nikolai", "Ivanov Nikolai", "ivanov.nikolai@mail.ru"),
    ("petrov_elena", "Petrov Elena", "petrov.elena@mail.ru"),
    # Brazilian
    ("silva_paulo", "Silva Paulo", "silva.paulo@gmail.com.br"),
    ("santos_carla", "Santos Carla", "santos.carla@gmail.com.br"),
    # Indian
    ("sharma_raj", "Sharma Raj", "sharma.raj@gmail.in"),
    ("kumar_priya", "Kumar Priya", "kumar.priya@gmail.in"),
    # Korean
    ("kim_sung", "Kim Sung", "kim.sung@naver.com"),
    ("park_hye", "Park Hye", "park.hye@naver.com"),
    # Thai
    ("somchai_david", "Somchai David", "somchai.david@gmail.co.th"),
    ("sirinual_nok", "Sirinual Nok", "sirinual.nok@gmail.co.th"),
]

# Fun chat messages for different contexts
CHAT_MESSAGES = [
    "Nice community!",
    "Great pixel art!",
    "Who's creating this canvas?",
    "Love the colors!",
    "Is anyone else working on this section?",
    "Let's create something together!",
    "Amazing work everyone!",
    "Fun to draw together!",
    "Keep it up!",
    "Beautiful design!",
    "This is so cool!",
    "Great team effort!",
    "Looking good!",
    "More pixels incoming!",
    "Can't wait to see the final result!",
    "This is addictive!",
    "Great collaborative art!",
    "Love pixel wars!",
    "Epic community!",
    "Let's make history!",
]

# Color palette for pixels
COLORS = [
    "#FF0000",  # Red
    "#00FF00",  # Green
    "#0000FF",  # Blue
    "#FFFF00",  # Yellow
    "#FF00FF",  # Magenta
    "#00FFFF",  # Cyan
    "#FFA500",  # Orange
    "#800080",  # Purple
    "#FFC0CB",  # Pink
    "#A52A2A",  # Brown
    "#FF69B4",  # Hot Pink
    "#4B0082",  # Indigo
    "#FF4500",  # Orange Red
    "#2E8B57",  # Sea Green
    "#DC143C",  # Crimson
    "#20B2AA",  # Light Sea Green
    "#32CD32",  # Lime Green
    "#FFD700",  # Gold
    "#4169E1",  # Royal Blue
    "#FF1493",  # Deep Pink
]


class Command(BaseCommand):
    help = (
        "Populate test data: loads pixels from global-canvas-prepropulate.json, "
        "distributes them across all test users, and saves to the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--communities",
            type=str,
            default="9,10",
            help="Comma-separated community IDs for local memberships (default: 9,10)",
        )

    def handle(self, *args, **options):
        # ── 1. Load test users ──────────────────────────────────────────────
        users = User.objects.filter(
            username__in=[u[0] for u in USERS_DATA]
        ).select_related("profile")

        if not users.exists():
            self.stdout.write(
                self.style.ERROR("No test users found. Run the initial import first.")
            )
            return

        user_list = list(users)
        self.stdout.write(
            self.style.SUCCESS(f"✓ Found {len(user_list)} test users")
        )

        # ── 2. Resolve communities ──────────────────────────────────────────
        community_ids = [
            int(cid.strip()) for cid in options["communities"].split(",")
        ]
        communities = list(Community.objects.filter(id__in=community_ids))
        if len(communities) != len(community_ids):
            found_ids = [c.id for c in communities]
            self.stdout.write(
                self.style.ERROR(
                    f"Not all communities found. "
                    f"Required: {community_ids}, Found: {found_ids}"
                )
            )
            return

        global_community = Community.objects.filter(slug="global").first()
        if not global_community:
            self.stdout.write(self.style.ERROR("Global community not found."))
            return

        self.stdout.write(
            self.style.SUCCESS(f"✓ Global community: {global_community.name}")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Local communities: {[c.name for c in communities]}"
            )
        )

        # ── 3. Add users to all communities ────────────────────────────────
        all_communities = communities + [global_community]
        for user in user_list:
            for community in all_communities:
                _, created = CommunityMembership.objects.get_or_create(
                    user=user,
                    community=community,
                    defaults={"active": True},
                )
                if created:
                    self.stdout.write(
                        f"  ✓ Added {user.username} → {community.name}"
                    )

        # ── 4. Load pixels from JSON ────────────────────────────────────────
        if not CANVAS_JSON.exists():
            self.stdout.write(
                self.style.ERROR(f"JSON file not found: {CANVAS_JSON}")
            )
            return

        raw = json.loads(CANVAS_JSON.read_text(encoding="utf-8"))
        # Support both list-of-dicts and dict-of-lists
        if isinstance(raw, list):
            pixel_entries = [(int(p["x"]), int(p["y"]), str(p["color"])) for p in raw]
        else:
            self.stdout.write(self.style.ERROR("Unexpected JSON format."))
            return

        total = len(pixel_entries)
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Loaded {total} pixels from JSON")
        )

        # ── 5. Distribute pixels across all users (round-robin) ─────────────
        # Shuffle so pixel regions aren't tied to insertion order
        pixel_entries_shuffled = pixel_entries[:]
        random.shuffle(pixel_entries_shuffled)

        n_users = len(user_list)
        now = timezone.now()

        pixel_objs = []
        action_objs = []

        for idx, (x, y, color) in enumerate(pixel_entries_shuffled):
            owner = user_list[idx % n_users]
            # Spread timestamps: most recent pixels at the front, older ones later
            days_ago = (idx / total) * 30          # 0 → 30 days ago
            hours_jitter = random.randint(0, 23)
            ts = now - timedelta(days=days_ago, hours=hours_jitter)

            pixel_objs.append(
                Pixel(community=global_community, x=x, y=y, color=color)
            )
            action_objs.append(
                UserAction(
                    community=global_community,
                    user_key=f"user:{owner.id}",
                    x=x,
                    y=y,
                    color=color,
                    accepted=True,
                    created_at=ts,
                )
            )

        # ── 6. Bulk-save to database ────────────────────────────────────────
        self.stdout.write("  Saving pixels and user actions to database…")
        with transaction.atomic():
            saved_pixels = Pixel.objects.bulk_create(
                pixel_objs, batch_size=500, ignore_conflicts=True
            )
            saved_actions = UserAction.objects.bulk_create(
                action_objs, batch_size=500, ignore_conflicts=True
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Saved {len(saved_pixels)} pixels to database"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Saved {len(saved_actions)} user actions to database"
            )
        )

        # ── 7. Summary & rankings ──────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("✓ Done!"))
        self.stdout.write(
            f"  Total pixels in global canvas: "
            f"{Pixel.objects.filter(community=global_community).count()}"
        )

        self.stdout.write(self.style.SUCCESS("\n🏆 Global Canvas Rankings (all users):"))
        rankings = (
            UserAction.objects
            .filter(
                community=global_community,
                user_key__startswith="user:",
                accepted=True,
            )
            .values("user_key")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        for i, row in enumerate(rankings, 1):
            try:
                uid = int(row["user_key"].split(":")[1])
                u = next((x for x in user_list if x.id == uid), None)
                name = u.username if u else f"user:{uid}"
            except (ValueError, IndexError):
                name = row["user_key"]
            self.stdout.write(f"   {i:2}. {name}: {row['count']} pixels")

        self.stdout.write(self.style.SUCCESS("=" * 60))
