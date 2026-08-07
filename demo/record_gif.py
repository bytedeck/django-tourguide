"""Record the README's demo GIF from the running demo site.

    python demo/manage.py runserver 127.0.0.1:8011
    python demo/record_gif.py tour.gif [base-url]

Needs `playwright` and `pillow`, which are not project dependencies: this is a tool for
producing one asset, not part of the package or its tests. Set `TOURGUIDE_CHROMIUM` if the
browser is provided by the environment rather than by `playwright install`.

Every frame is a real screenshot of the real app. Nothing is drawn on top: no captions, no
composited browser chrome. The story is chosen so it reads without narration, and so that the
two things a single-page tour cannot do are both visible:

    welcome -> anchored step -> anchored step -> the tour crosses to the Settings page
    -> that page is reloaded and the tour is still on the same step -> last step

Frames are captured back to back, and identical ones collapse into one frame with a longer
duration when the GIF is written, which is what produces the pauses.
"""

import io
import os
import pathlib
import subprocess
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "tour.gif")
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8011"

REPO = pathlib.Path(__file__).resolve().parent.parent
MANAGE = REPO / "demo" / "manage.py"

#: Wide enough for the popover and what it points at, short enough that the GIF is not mostly
#: empty page. No device scale factor: this is a README asset, not a print one.
VIEWPORT = {"width": 1000, "height": 620}

#: Milliseconds per captured frame, and the GIF's frame duration.
FRAME_MS = 110

#: A browser the environment already provides. Unset, which is the normal case, means the one
#: Playwright manages itself.
CHROMIUM = os.environ.get("TOURGUIDE_CHROMIUM")

#: Narrower than captured, which roughly halves the file for no loss a reader would notice.
WIDTH = 800

frames = []


def shoot(page, count=1):
    """Take `count` screenshots back to back, which is what makes the motion."""
    for _ in range(count):
        frames.append(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))


def hold(page, count):
    """Linger on the current state long enough to read it."""
    page.wait_for_timeout(FRAME_MS)
    shoot(page, count)


def through(page, count):
    """Capture a transition as it happens, rather than only its endpoints."""
    for _ in range(count):
        page.wait_for_timeout(FRAME_MS)
        shoot(page)


def reset_progress():
    """Start from an unseen tour, so the recording opens on the first step."""
    subprocess.run(
        [sys.executable, str(MANAGE), "shell", "-c",
         "from tourguide.progress.models import TourProgress; TourProgress.objects.all().delete()"],
        cwd=REPO, check=True, capture_output=True,
    )


def record(page):
    """Walk the demo tour, capturing as it goes."""
    page.goto(f"{BASE}/admin/login/?next=/")
    page.fill("#id_username", "demo")
    page.fill("#id_password", "demo")
    page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")

    # Bootstrap 5, because a themed popover is what a host project actually sees. The choice is
    # kept in the session, so it survives the tour's own navigation.
    page.goto(f"{BASE}/?bs=5")
    page.wait_for_selector(".driver-popover-next-btn", timeout=10000)
    page.wait_for_timeout(400)
    hold(page, 14)

    for _ in range(2):                              # the two anchored steps on this page
        page.click(".driver-popover-next-btn")
        through(page, 8)
        hold(page, 12)

    page.click(".driver-popover-next-btn")          # crosses to the Settings page
    through(page, 16)
    page.wait_for_selector(".driver-popover", timeout=10000)
    hold(page, 14)

    page.reload()                                   # and the tour is still on that step
    through(page, 16)
    page.wait_for_selector(".driver-popover", timeout=10000)
    hold(page, 16)

    page.click(".driver-popover-next-btn")          # last step
    through(page, 8)
    hold(page, 18)


def write(path):
    """Quantise and save the captured frames as one looping GIF."""
    scaled = [f.resize((WIDTH, round(f.height * WIDTH / f.width)), Image.LANCZOS) for f in frames]
    # One palette for the whole animation. Per-frame palettes would track colour more closely,
    # but the page is flat colour and a shared palette is what lets frames compress against
    # each other rather than each carrying its own table.
    palette = scaled[0].quantize(colors=128, method=Image.MEDIANCUT)
    quantized = [f.quantize(palette=palette, dither=Image.FLOYDSTEINBERG) for f in scaled]
    quantized[0].save(
        path, save_all=True, append_images=quantized[1:], duration=FRAME_MS, loop=0, optimize=True,
    )


reset_progress()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    record(browser.new_context(viewport=VIEWPORT).new_page())
    browser.close()

write(OUT)
print(f"{OUT}: {len(frames)} frames captured, {OUT.stat().st_size / 1_000_000:.2f} MB, {WIDTH}px wide")
