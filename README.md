# Pelican 1606 Organizer - Windows App Build

This folder builds your CAD tool into a real double-clickable Windows
program (`PelicanOrganizer.exe`) — no Python install on your Windows
machine required, ever.

## How it works

You can't cross-compile a Windows `.exe` from a Linux machine when the
program depends on a big compiled library like CadQuery (it needs
Windows-native binaries). The reliable, free way around that is to let
GitHub build it for you on an actual Windows machine in the cloud
(GitHub Actions), then you just download the finished `.exe`. You never
install Python — GitHub's temporary build machine does.

Total time: about 5 minutes of clicking, then a 3-5 minute automatic
build.

## Steps

1. **Create a free GitHub account** (skip if you already have one):
   https://github.com/signup

2. **Create a new repository**:
   - Go to https://github.com/new
   - Name it something like `pelican-organizer`
   - Leave it Public or Private, doesn't matter
   - Click "Create repository" (don't add a README/gitignore — leave defaults)

3. **Upload these files**:
   - On your new repo's page, click "uploading an existing file" (or
     "Add file" -> "Upload files")
   - Drag the *entire contents* of this folder in — including the
     hidden-looking `.github` folder with `workflows/build-windows.yml`
     inside it. If your browser/OS won't drag a folder with a dot in
     its name, use "Add file" -> "Create new file" and type
     `.github/workflows/build-windows.yml` as the filename, then paste
     that file's contents in.
   - Commit the upload.

4. **Let it build**:
   - Click the "Actions" tab at the top of your repo.
   - You should see a run called "Build Windows EXE" already running
     (it starts automatically on upload). If it's not there, click
     "Build Windows EXE" on the left, then "Run workflow".
   - Wait for the green checkmark (a few minutes).

5. **Download your app**:
   - Click into the finished run.
   - Scroll down to "Artifacts" and download `PelicanOrganizer-windows-exe`
     (a small zip file).
   - Unzip it — inside is `PelicanOrganizer.exe`.
   - Double-click it. That's your app. No installer, no Python, nothing
     else needed. (First launch takes a few seconds longer than normal —
     that's the `.exe` unpacking itself into a temp folder, which it
     does every time since this is a single-file build.)

## If the build fails (red X instead of green check)

Click into the failed run, open the "Build EXE with PyInstaller" step,
and copy the red error text back to me — I'll adjust the workflow or
script and you re-upload just the changed file.

## Using the app

- Set the panel Length/Width/Thickness (defaults match a Pelican 1606
  lid interior).
- Toggle the Gridfinity baseplate grid, restrict it to one quadrant,
  and add magnet holes if you want them.
- Pick an output folder (defaults to your Desktop).
- Click "Generate & Export STEP Files". It writes one STEP file per
  quadrant (plus STL if you checked that box) to the folder you chose.
