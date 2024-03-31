# `gphoto2`-based Eclipse Automation

A few quick notes:
* Use at your own risk, I cannot warrant anything -- that the script will actually work, or produce appropriate exposures, or prevent your camera sensor or lenses from burning up in smoke.
* Script has never been field-tested, just a few short dry runs with artificial timings on my specific camera (a Canon EOS 50D)
* It is not advisable to look at the partial phase, diamond ring, Baily's Beads, or [anything other than totality](https://www.covingtoninnovations.com/michael/blog/1708/170819-AAS-Chou-Solar-Eclipse-Eye-Safety.pdf) without a filter. I am not responsible for your eyesight!
* The script is dirty. I do not want to refactor it since testing it is not easy.
* The script requires `gphoto2` and `festival` speech-synthesis engine invokable on the command-line
* Check the script works in your environment with your camera before using it on the field
* Ensure the timings of the contacts are correctly listed as it varies drastically with exact location
* Tweak the exposures and timings as you deem fit

A few trade-offs I made:
* I could not figure out how to make the camera take burst exposures reliably with `gphoto2`, so I settled for slow coverage of Baily's Beads and Diamond Ring to avoid the risk of the script failing. A second rig with burst exposures (or video) taken right at the Diamond Ring and Baily's Beads moments will serve that purpose better.
* I could not figure out how to save the exposures on the camera to avoid the overhead of transfer. This is likely because of [this issue](https://github.com/gphoto/libgphoto2/issues/755)

Please [let me know](mailto:akarsh@kde.org) if you found this script useful on the field, and provide any tweaks necessary to get it to work.

## Dependencies
I'm trying to list everything I can think of, there may be missing stuff. Please test in your environment.

* System dependencies: `gphoto2`, `festival`, `Python >= 3.10`
* Python dependencies: `tqdm`
