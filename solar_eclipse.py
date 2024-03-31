#!/usr/bin/env python3

import datetime
import os
import subprocess
import time
import tqdm
import sys
import math
from enum import Enum

"""
Python Script to use gphoto2 to control a camera to capture a Total Solar Eclipse

During a total solar eclipse, there are many fleeting events that need rapid
response with different settings on the camera. Moreover, the dynamic range of
totality itself is enormous, requiring many different exposures. This script is
designed to orchestrate the camera's exposures so that you can enjoy the
eclipse instead.

The camera has to be tracking the sun and has to be on Manual Mode. There must
be enough disk space on the computer controlling the camera since images are
transferred (due to problems with Gphoto2). The timings of the eclipse contacts
must be set accurately.

Filter must be manually removed during diamond ring C2 and replaced during
diamond ring C3.

NO WARRANTY ON THIS SCRIPT. IT HAS NEVER BEEN TESTED. USE AT YOUR OWN RISK.
"""

# SPECIFY THE DATE OF THE ECLIPSE IN UTC
DATE = (2024, 4, 8)

DATE = (2024, 3, 31) # FIXME: TESTING ONLY, comment out!!!

class Timings:
    Custom = [
        (4, 28, 0), # First contact (H, M, S)
        (4, 32, 0), # Second contact (H, M, S)
        (4, 33, 0), # Third contact (H, M, S)
        (4, 37, 0), # Fourth contact (H, M, S)
    ]

DEFINE_TIMINGS_UTC = Timings.Custom # PICK THE CORRECT CONTACT TIMINGS!

# Diamond Ring and Bailey's Beads settings
DIAMOND_RING = 30 # Go into diamond ring mode at C2/C3 ± these many seconds
BAILEYS_BEADS = 10 # Go into Bailey's beads mode at C2/C3 ± these many seconds

# This is the path of the directory where eclipse images will be saved
TARGET_DIR='Eclipse'

# In this script, I define EV := log2(ISO * Exposure Time / Aperture^2)
# For example, f/10 and 1/320" exposure at ISO 200 will have EV = log2(200 /
# (10^2 * 320)) = -7.3
#
# The chosen settings (which you may have to vary for your specific camera and
# lens) are based on Xavier Jubier's calculator
# http://xjubier.free.fr/en/site_pages/SolarEclipseExposure.html and Fred
# Espenak's table
# https://www.cloudynights.com/topic/911786-what-exposure-for-diamond-ring-and-baileys-bead/?p=13278090

class Config:
    Bracketing ='/main/capturesettings/aeb'
    Aperture = '/main/capturesettings/aperture'
    ShutterSpeed = '/main/capturesettings/shutterspeed'
    EV = '/main/capturesettings/exposurecompensation'
    ISO = '/main/imgsettings/iso'

class Bracketing(Enum):
    # Obtained through `gphoto2 --get-config "/main/capturesettings/aeb"`
    OFF = 0
    EV_0_1_3 = 1
    EV_0_2_3 = 2
    EV_1 = 3
    EV_1_1_3 = 4
    EV_1_2_3 = 5
    EV_2 = 6

class Settings:
    """
    Base class for settings for each phase

    interval: Used for partial and total phases, specifies the approximate maximum interval between exposure sets; ignored in Bailey's Beads/Diamond Ring phases
    index: Internal counter to cycle between exposure settings for a given phase
    bracketing: Bracketing setting to use for this phase
    aperture: Union[List[str], str], specifying the aperture(s) to use for the exposures. Lists are cycled through.
    speed: Union[List[str], str], specifying the shutter speed(s) to use for the exposures. Lists are cycled through.
    iso: Union[List[int], int], specifying the ISO(s) to use for the exposures. Lists are cycled through.
    """
    interval = 0
    index = 0 # Tracks which setting is to be used

    # Run gphoto2 --get-config /main/capturesettings/aperture to get aperture options
    aperture = "4.5"

    bracketing = Bracketing.OFF

    # Run gphoto2 --get-config /main/capturesettings/shutterspeed to get shutter speed options
    speed = "1/8000"

    iso = 200

    triggered = True

# Define the exposures for the various phases. Note that each of the phases has
# some custom handling
class Phases:
    class Partial(Settings):
        # Per my experience with the partial phase of the 2023 annular eclipse,
        # EV = -5.7 works well for my filter. This varies depending on the
        # filter used. This annularity was lower in the sky and I may need to
        # lower the EV a bit to account for less extinction.
        # Fred Espenak recommends -8, Xavier Jubier recommends -9
        name='Partial'
        interval = 120 # Take a photo every 2 minutes
        aperture = "8" # f/10 (filtered)
        bracketing = Bracketing.EV_1_1_3 # ±1⅓
        speed = "1/250" # EV = -6.3, brackets should yield = -5.3 and -7.3

    class Diamond(Settings):
        name='DiamondRing'

        # Diamond ring is a longer exposure. Fred Espenak recommends -5,
        # Xavier Jubier -6.3. Therefore I place the central bracket of the
        # entire sequence in this range. f/18 with my lens will produce
        # diffraction spikes, f/8 will not produce good spikes.

        # The brackets will be EV = -3, -4, -5 at f/8, -5.3, -6.3, -7.3 at
        # f/16.

        iso = 400
        bracketing = Bracketing.EV_1 # ±1
        speed = "1/100"
        aperture = ["8", "18"]

    class Baileys(Settings):
        name='Baileys'

        # Bailey's Beads is a short exposure. Fred Espenak recommends -11,
        # Xavier Jubier -12. f/16 with my lens will produce diffraction spikes,
        # f/8 will not produce good spikes.

        # The brackets will be EV = -13, -12, -11 (f/16), -10, -9, -8 (f/8)

        iso = 200
        aperture = ["16", "8"]
        bracketing = Bracketing.EV_1_2_3 # ±1⅔
        speed = "1/3200"

    class Totality(Settings):
        name='Totality'
        bracketing = Bracketing.OFF
        interval = 5
        # From my 2017 experience EV = -1.26 captured the corona to about 2 solar radii. Fred Espenak recommeds 0 for the same.
        # EV = 2.6 shows some earthshine hints, so should be covered with EV = 4.3
        aperture, speed, iso = zip(
            ("11", "1/6400", 200), # Backup Bracket    [EV: -11.9]
            ("11", "1/3200", 200), # Chromosphere      [EV: -10.9]
            ("11", "1/1600", 200), # Prominences       [EV: -9.9]
            ("10", "1/500", 200),  # Lower Corona      [EV: -8.0]
            ("10", "1/60", 200),   # Inner Corona      [EV: -4.9]
            ("8",  "1/25", 400),   # Middle Corona     [EV: -2.0]
            ("6.3", "1/10", 400),  # Outer Corona      [EV: 0.0]
            ("6.3", "0.5", 400),   # Far Outer Corona  [EV: 2.3]
            ("6.3", "1", 400),     # Earthshine        [EV: 3.3]
            ("6.3", "4", 200),     # Earthshine        [EV: 4.3]
        )


def click_(aperture: str, speed: str, iso: int, phase: Phases):
    """
    Note: I found that there are issues of the camera going into busy mode and having PTP transactions fail in trying to do anything else, such as:
        1. Using --trigger-capture to rapidly shoot burst frames
        2. Storing files on CF card memory

    This is slow and does not get the best coverage possible for diamond ring
    and Bailey's Beads, but it is better than the script failing due to some
    PTP error and not taking any pictures at all. With these settings, my Canon
    50D manages about 15 frames (i.e. 5 stacks) during the 20 seconds assigned
    to Diamond Ring at each contact, and 15 frames (i.e. 5 stacks) during the
    20 seconds assigned to Bailey's Beads at each contact.

    """
    filename = os.path.join(TARGET_DIR, f'{phase.name}_t{int(time.time())}_%n')
    bracketing = phase.bracketing
    try:
        EV = math.log(iso * eval(speed) / float(aperture)**2)/math.log(2)
        print(f'Exposure Value: {EV:0.2f}')
    except Exception as e:
        print('Minor exception calculating EV: {e}')
    cmd = f"gphoto2 --set-config-value {Config.Aperture}={aperture} --set-config-value {Config.ShutterSpeed}={speed} --set-config-value {Config.ISO}={iso} --set-config {Config.Bracketing}={bracketing.value} --set-config capturetarget=0 --force-overwrite --filename='{filename}' --no-keep --capture-image-and-download"
    if bracketing != Bracketing.OFF:
        cmd += " --capture-image-and-download --capture-image-and-download"
    print(cmd)
    os.system(cmd)

def click(phase: Phases):
    """Note: The cycling mechanism is designed to abandon the cycle
    whenever time runs out on the phase. For phases other than
    totality, we resume from where we stopped in C1/C2 during
    C3/C4."""
    click_(
        phase.aperture[phase.index%len(phase.aperture)] if isinstance(phase.aperture, (list, tuple)) else phase.aperture,
        phase.speed[phase.index%len(phase.speed)] if isinstance(phase.speed, (list, tuple)) else phase.speed,
        phase.iso[phase.index%len(phase.iso)] if isinstance(phase.iso, (list, tuple)) else phase.iso,
        phase=phase)
    phase.index += 1


def main():

    def say(text: str): # Thank you ChatGPT
        try:
            say.festival_proc
        except AttributeError:
            say.festival_proc = subprocess.Popen(['festival', '--pipe'], stdin=subprocess.PIPE)
        print(text)
        say.festival_proc.stdin.write(f'(SayText "{text}")\n'.encode())
        say.festival_proc.stdin.flush()

    if not os.path.isdir(f'{TARGET_DIR}'):
        os.makedirs(f'{TARGET_DIR}')

    phase = None
    TIMES = [datetime.datetime(*DATE, *time, 0, datetime.timezone.utc) for time in DEFINE_TIMINGS_UTC]
    C1 = TIMES[0]
    C4 = TIMES[3]
    C2 = TIMES[1]
    C3 = TIMES[2]

    today = datetime.datetime.utcnow().date()
    if C1.date() != today:
        print(f'!!!! Warning: Eclipse does not seem to be today, i.e. {today} !!!!')
        say("Warning, eclipse does not seem to be today! Please check!")

    if os.system("gphoto2 --get-config /main/capturesettings/focusmode | grep -q 'Current: Manual'") != 0:
        say("Camera seems to be in auto-focus. Please manually focus. Goodbye!")
        sys.exit(1)

    if os.system("gphoto2 --get-config /main/capturesettings/drivemode | grep -q 'Current: Single'") != 0:
        say("Camera not in single shot drive. Please check that this is intended!")

    say("Please check that the camera is in manual mode")

    now = lambda: datetime.datetime.now(tz=datetime.timezone.utc)
    seconds = lambda x: datetime.timedelta(seconds=x)
    say("Please check the times of the contacts printed")
    for i, t in enumerate(TIMES):
        print(f'{i+1}th contact at {t.ctime()} UTC in {(t - now()).total_seconds()/60.0:0.2f} minutes')

    say('Entering sequence loop')

    C2_DR = C2 - seconds(DIAMOND_RING)
    C2_BB = C2 - seconds(BAILEYS_BEADS)
    C2_BB2 = C2 + seconds(BAILEYS_BEADS)
    C3_DR = C3 + seconds(DIAMOND_RING)
    C3_BB = C3 + seconds(BAILEYS_BEADS)
    C3_BB2 = C3 - seconds(BAILEYS_BEADS)

    if now() > C4:
        say("It is after fourth contact. Nothing to do. Goodbye!")
        time.sleep(10)
        return

    pbar_c1 = None
    pbar_c2 = None
    pbar_c3 = None
    pbar_c4 = None

    for phase in (Phases.Partial, Phases.Diamond, Phases.Baileys, Phases.Totality):
        phase.N = max(len(option) if isinstance(option, (list, tuple)) else 1 for option in (phase.aperture, phase.iso, phase.speed))

    while True:

        try:

            while now() < C1 or now() > C4:
                if now() < C1 and pbar_c1 is None:
                    pbar_c1 = tqdm.tqdm(total=int((C1 - now()).total_seconds()), desc='(Waiting) C1')
                if phase is not None:
                    say('Camera entering resting phase')
                    phase = None
                time.sleep(5) # Long delays are okay
                # Nothing to do
                try:
                    dt = int((C1 - now()).total_seconds())
                    pbar_c1.update(pbar_c1.total - dt - pbar_c1.n)
                except:
                    pass
                if now() > C4:
                    say('Fourth contact over. Exiting program')
                    sys.exit(0)


            c2dr_countdown = set()
            while (now() < C2_DR and now() >= C1) or (now() > C3_DR and now() <= C4):  # Partial phase, C1 to C2 or C3 to C4
                if pbar_c1 is not None:
                    pbar_c1.close()
                if pbar_c3 is not None:
                    pbar_c3.close()

                if pbar_c2 is None and now() < C2_DR:
                    pbar_c2 = tqdm.tqdm(total=int((C2_DR - now()).total_seconds()), desc='(Partial) C2 DR')

                if pbar_c4 is None and now() > C3_DR:
                    pbar_c4 = tqdm.tqdm(total=int((C4 - now()).total_seconds()), desc='(Partial) C4')

                if now() < C2_DR:
                    try:
                        dt = int((C2_DR - now()).total_seconds())
                        pbar_c2.update(pbar_c2.total - dt - pbar_c2.n)
                    except:
                        pass

                if now() > C3_DR:
                    try:
                        dt = int((C4 - now()).total_seconds())
                        pbar_c4.update(pbar_c4.total - dt - pbar_c4.n)
                    except:
                        pass

                time.sleep(0.5)
                if phase != Phases.Partial:
                    say('Camera entering partial phase. Please ensure filter is on!')
                    phase = Phases.Partial
                if int(time.time()) % phase.interval == 0:
                    print('Clicking partial phase exposure')
                    phase.triggered = True
                if phase.triggered:
                    click(phase)
                    if phase.index % phase.N == 0:
                        phase.triggered = False

                dt = int((C2_DR - now()).total_seconds())
                if dt > 0 and dt < 60 and int(dt) % 10 == 0 and int(dt) not in c2dr_countdown:
                    say(f'Prepare camera for filter off in {int(dt)} seconds')
                    c2dr_countdown.add(int(dt))

            while (now() > C2_DR and now() <= C2_BB) or (now() >= C3_BB and now() < C3_DR):
                time.sleep(0.05)
                if phase != Phases.Diamond:
                    say('Camera entering diamond ring phase. Ensure filter is off!')
                    phase = Phases.Diamond
                click(phase)

            while (now() > C2_BB and now() <= C2_BB2) or (now() >= C3_BB2 and now() < C3_BB):
                time.sleep(0.05)
                if phase != Phases.Baileys:
                    say('Camera entering Bailey phase. Ensure filter is off!')
                    phase = Phases.Baileys
                click(phase)

            while (now() > C2_BB2 and now() < C3_BB2):
                try:
                    if pbar_c3 is None:
                        pbar_c3 = tqdm.tqdm(total=int((C3_BB2 - now()).total_seconds()), desc='(Total) C3')
                    pbar_c3.update(pbar_c3.total - int((C3_BB2 - now()).total_seconds()) - pbar_c3.n)
                except:
                    pass
                time.sleep(0.1)
                if phase != Phases.Totality:
                    say('Camera entering totality! Ensure filter is off!')
                    phase = Phases.Totality

                if int(time.time()) % phase.interval == 0:
                    print('Clicking totality exposure')
                    phase.triggered = True

                if phase.triggered:
                    click(phase)
                    if phase.index % phase.N == 0:
                        phase.triggered = False
        except Exception as e:
            say('Encountered exception!')
            print(e, file=sys.stderr)


if __name__ == "__main__":
    main()
