# The 3D tutor

`index.html` hosts the Unity WebGL tutor. The agent page embeds it transparent beside the chat
(`client/src/Avatar.jsx`) and tells it over `postMessage` what to say. It fetches each spoken
sentence from the API's `/v1/tts`. Students can hide it with a button in the chat's header, and
while it is hidden the page pauses Unity's main loop, so it stops rendering.

The Unity build is not in git. Build the tutor's Unity project for WebGL, then install the
output here:

```bash
avatar/install.sh ~/Builds/WebGL
```

That copies the build into `avatar/build/` under fixed names, writes `build/build.json` with
the build's version, and swaps the new build in whole. Until a build is installed the page shows
no tutor, and the chat works as it always does.

The Unity project lives in InviteInstitute/vex-pedagogical-agent (`unity/`, Unity 2022.3).
