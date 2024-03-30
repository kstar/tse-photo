#!/usr/bin/env python3

import datetime
import os
import subprocess
import time
import tqdm
import sys
import math
from enum import Enum

DATE = (2024, 4, 8)

DATE = (2024, 3, 30) # FIXME: TESTING ONLY, comment out!!!

class Timings:
    Custom = [
        (5, 3, 0), # First contact (H, M, S)
        (5, 15, 0), # Second contact (H, M, S)
        (5, 18, 0), # Third contact (H, M, S)
        (5, 25, 0), # Fourth contact (H, M, S)
    ]

DEFINE_TIMINGS_UTC = Timings.Custom

DIAMOND_RING = 30 # Go into diamond ring mode at C2/C3 ± these many seconds
BAILEYS_BEADS = 10 # Go into Bailey's beads mode at C2/C3 ± these many seconds
TARGET_DIR='Eclipse'

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
    interval = 0

    # Run  !gphoto2 --get-config /main/capturesettings/aperture to get aperture options
    aperture = "4.5"

    bracketing = Bracketing.OFF
    speed = "1/8000"

    iso = 200

class Phases:
    class Partial(Settings):
        name='Partial'
        interval = 120 # Take a photo every 2 minutes
        aperture = "10" # f/10 (filtered)
        bracketing = Bracketing.EV_1 # ±1
        speed = "1/1000"

    class Diamond(Settings):
        name='DiamondRing'
        bracketing = Bracketing.EV_1 # ±1
        speed = "1/1000"
        aperture = ["8", "16"]

    class Baileys(Settings):
        name='Baileys'
        aperture = ["16", "8"]
        bracketing = Bracketing.EV_1_2_3 # ±1⅔
        speed = "1/3200"

    class Totality(Settings):
        name='Totality'
        bracketing = Bracketing.OFF
        interval = 5
        delay_compensation = 3
        exposures = [
            ("16", "1/1600", 200), # Chromosphere    [EV: 18.6]
            ("11", "1/1600", 200), # Prominences     [EV: 17.6]
            ("10", "1/500", 200),  # Lower Corona    [EV: 15.6]
            ("10", "1/60", 200),   # Inner Corona    [EV: 12.5]
            ("8",  "1/25", 400),   # Middle Corona   [EV: 9.6]
            ("6.3", "1/10", 400),  # Outer Corona    [EV: 7.6]
            ("6.3", "0.5", 400), # Far Outer Corona  [EV: 5.3]
            ("6.3", "1", 400),   # Earthshine        [EV: 4.3]
            ("6.3", "4", 200),   # Earthshine        [EV: 2.3]
        ]


def click(aperture: str, speed: str, iso: int, phase: Phases):
    filename = os.path.join(TARGET_DIR, f'{phase.name}_t{int(time.time())}_%n')
    bracketing = phase.bracketing
    cmd = f"gphoto2 --set-config-value {Config.Aperture}={aperture} --set-config-value {Config.ShutterSpeed}={speed} --set-config-value {Config.ISO}={iso} --set-config {Config.Bracketing}={bracketing.value} --set-config capturetarget=0 --force-overwrite --filename='{filename}' --no-keep --capture-image-and-download"
    if bracketing != Bracketing.OFF:
        cmd += " --capture-image-and-download --capture-image-and-download"
    print(cmd)
    os.system(cmd)

def set_bracketing(bracketing: Bracketing):
    os.system(f"gphoto2 --set-config {Config.Bracketing}={bracketing.value}")


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

    if TIMES[0].date() != datetime.datetime.today().date():
        print(f'!!!! Warning: Eclipse does not seem to be today, i.e. {datetime.datetime.today().date()} !!!!')
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

    C1 = TIMES[0]
    C4 = TIMES[3]
    C2 = TIMES[1]
    C3 = TIMES[2]
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

    dr_index = 0
    bb_index = 0

    pbar_c1 = None
    pbar_c2 = None
    pbar_c3 = None
    pbar_c4 = None
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
                    set_bracketing(phase.bracketing)
                if int(time.time() % Phases.Partial.interval) == 0:
                    print('Clicking partial phase exposure')
                    click(phase.aperture, phase.speed, phase.iso, phase=phase)

                dt = int((C2_DR - now()).total_seconds())
                if dt > 0 and dt < 60 and int(dt) % 10 == 0 and int(dt) not in c2dr_countdown:
                    say(f'Prepare camera for filter off in {int(dt)} seconds')
                    c2dr_countdown.add(int(dt))

            while (now() > C2_DR and now() <= C2_BB) or (now() >= C3_BB and now() < C3_DR):
                time.sleep(0.05)
                if phase != Phases.Diamond:
                    say('Camera entering diamond ring phase. Ensure filter is off!')
                    phase = Phases.Diamond
                    set_bracketing(phase.bracketing)
                click(phase.aperture[dr_index%2], phase.speed, phase.iso, phase=phase)
                dr_index += 1

            while (now() > C2_BB and now() <= C2_BB2) or (now() >= C3_BB2 and now() < C3_BB):
                time.sleep(0.05)
                if phase != Phases.Baileys:
                    say('Camera entering Bailey phase. Ensure filter is off!')
                    phase = Phases.Baileys
                    set_bracketing(phase.bracketing)
                click(phase.aperture[bb_index%2], phase.speed, phase.iso, phase=phase)
                bb_index += 1

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
                    set_bracketing(phase.bracketing)
                for exposure in phase.exposures:
                    click(*exposure, phase=phase)
                dt = (C3_BB2 - now()).total_seconds()
                if dt < 0:
                    continue
                if dt > phase.interval + phase.delay_compensation:
                    time.sleep(phase.interval)
                else:
                    time.sleep(dt + 0.5) # Force entry into Bailey's Beads
        except Exception as e:
            say('Encountered exception!')
            print(e, file=sys.stderr)


if __name__ == "__main__":
    main()
