---
name: INVITE Agent
description: A tutor that lives at the edge of a student's coding screen, dressed in ZANY's VEXcode VR look.
colors:
  vex-blue: "#4d90f0"
  vex-blue-deep: "#4382e4"
  vex-blue-soft: "#92bcec"
  gold: "#af883f"
  gold-button: "#b18c40"
  gold-deep: "#937234"
  gold-edge: "#7d6026"
  gold-text: "#f6f1e6"
  reader: "#af127f"
  focus: "#1d5fd1"
  blue-text: "#163d73"
  blue-wash: "#edf3fd"
  workspace: "#f9f9f9"
  grey-wash: "#f1f4f8"
  white: "#ffffff"
  ink: "#1f2933"
  muted: "#5d6b7a"
  line: "#dde3ea"
  soft-edge: "#b8cad7"
  near-black: "#141414"
  pill: "#d6d6d6"
  cream: "#fff8df"
  alert: "#e8455a"
  alert-ink: "#8a1525"
  done: "#1f8a4c"
  unseen: "#8a96a3"
  dot: "#d9dee5"
typography:
  title:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.2
  headline:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.01em"
  body:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.5
  body-large:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 800
    letterSpacing: "0.06em"
  micro:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: "10.5px"
    fontWeight: 800
    letterSpacing: "0.05em"
  mono:
    fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  window: "6px"
  soft: "8px"
  tab: "10px"
  bubble: "14px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "18px"
components:
  title-bar:
    backgroundColor: "{colors.vex-blue}"
    textColor: "{colors.white}"
    typography: "{typography.headline}"
    height: "54px"
  tool-bar:
    backgroundColor: "{colors.vex-blue-soft}"
    textColor: "{colors.blue-text}"
    height: "52px"
  checkin-title-bar:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.white}"
    typography: "{typography.title}"
    height: "50px"
  gold-button:
    backgroundColor: "{colors.gold-button}"
    textColor: "{colors.near-black}"
    typography: "{typography.label}"
    rounded: "{rounded.window}"
    padding: "0 18px"
    height: "44px"
  help-button:
    backgroundColor: "{colors.reader}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.window}"
    padding: "0 14px"
    height: "36px"
  bar-button:
    textColor: "{colors.white}"
    rounded: "{rounded.window}"
    padding: "2px 6px 0"
    height: "46px"
  bar-button-light:
    textColor: "{colors.blue-text}"
    height: "44px"
  square-button:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.soft}"
    size: "34px"
  square-button-pressed:
    backgroundColor: "{colors.vex-blue-deep}"
    textColor: "{colors.white}"
  id-pill:
    backgroundColor: "{colors.vex-blue-deep}"
    textColor: "{colors.white}"
    rounded: "{rounded.soft}"
    padding: "4px 12px"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.body-large}"
    rounded: "{rounded.window}"
    padding: "0 12px"
    height: "44px"
  starter:
    backgroundColor: "{colors.white}"
    textColor: "{colors.blue-text}"
    rounded: "{rounded.pill}"
    padding: "8px 14px"
  starter-hover:
    backgroundColor: "{colors.blue-wash}"
  turn-student:
    backgroundColor: "{colors.focus}"
    textColor: "{colors.white}"
    typography: "{typography.body}"
    rounded: "{rounded.bubble}"
    padding: "10px 14px"
  turn-agent:
    backgroundColor: "{colors.grey-wash}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.bubble}"
    padding: "10px 14px"
  turn-checkin:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.ink}"
    rounded: "{rounded.bubble}"
    padding: "10px 14px"
  block-name:
    backgroundColor: "{colors.vex-blue}"
    textColor: "{colors.white}"
    rounded: "5px"
    padding: "0 7px"
  edge-tab:
    backgroundColor: "{colors.vex-blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.tab}"
    width: "40px"
  edge-tab-open:
    backgroundColor: "{colors.vex-blue-deep}"
---

# Design System: INVITE Agent

## Overview

**Creative North Star: "The Window at the Edge"**

The agent is one more window in ZANY's world. ZANY looks like VEXcode VR, so the agent does too. It uses Open Sans, VEX-blue title bars, gold bevelled buttons, small bold uppercase labels and floating windows with coloured title bars and a soft drop shadow. A student moves between the block editor, the playground and the agent and never sees the style change. Almost every colour value is ZANY's own, under ZANY's own name.

The code is the star, so the agent rests as a narrow VEX-blue tab on the right edge of the screen. Its name runs down the tab like a book's spine A check-in slides out of the tab as a small window with ZANY's gold title bar. Opened, the chat is a blue-titled window with a light-blue tool bar, a dotted workspace for the conversation and a white composer at the foot. It sits just left of the tab with the 3D tutor standing at its left edge.

The density is a classroom tool's. Controls are 44px tall, body text is 14.5px to 15px, and the type weights run heavy (600 to 800), because the readers are 12 years old on Chromebooks.

**Key Characteristics:**
- The visual language is borrowed whole from ZANY and VEXcode VR, never invented beside it.
- Windows are white slabs with a coloured title bar, 6px corners and one soft two-layer drop shadow.
- Buttons are physical, with a light top edge and a dark bottom bevel that presses in when clicked.
- Labels are small, bold and uppercase, the way ZANY labels its Student ID and level picker.
- The agent stays at the right edge until the student opens it.

## Colors

The palette is ZANY's. VEX blue carries structure, gold carries action and the check-in, and the reader magenta is kept for Help.

### Primary
- VEX Blue (#4d90f0) fills the chat's title bar, the edge tab, block-name chips, guide step markers and the typing dots. It is the colour of the agent's frame.
- Deep VEX Blue (#4382e4) is the pressed and open state. It fills the ID pill, a pressed square button and the edge tab while the chat is open.
- Soft VEX Blue (#92bcec) fills the tool bar under the title, the way ZANY's Code bar sits under its top bar.

### Secondary
- Button Gold (#b18c40) fills every primary action, such as Send, Reply and Sign in, and the chosen half of a two-way picker. Its edge is Gold Edge (#7d6026), which also colours the uppercase "Checking in" label inside a check-in bubble.
- Window Gold (#af883f) is the title bar of the check-in note, matching the title bar of ZANY's playground window. Gold Text (#f6f1e6) is the light ink that goes with it.

### Tertiary
- Reader Magenta (#af127f) is the Help button and nothing else. In ZANY it marks the reader, so here it marks the one button a stuck student should find.

### Neutral
- Workspace Grey (#f9f9f9) under a faint dot grid in Dot Grey (#d9dee5) is the background of the chat log, the sign-in screen and the placeholder before the coding environment loads.
- White (#ffffff) is every window body, input, composer and footer.
- Ink (#1f2933) is body text, and Muted Slate (#5d6b7a) is help text, field labels and quiet states.
- Line (#dde3ea) divides the composer and footer from the log and edges agent bubbles. Soft Edge (#b8cad7) outlines inputs, starter questions and notices.
- Focus Blue (#1d5fd1) is the focus ring, the caret, text buttons and the student's own chat bubbles. Blue Text (#163d73) is dark-blue text on light-blue surfaces, and Blue Wash (#edf3fd) is the hover fill and the info notice.
- Grey Wash (#f1f4f8) is the agent's chat bubble. Cream (#fff8df) is a check-in bubble and the warning notice.
- Pill Grey (#d6d6d6) is the unchosen half of a picker, and Near Black (#141414) is the text on gold.

### State colours
- Alert Red (#e8455a) marks the unread count on the tab, the recording state of the voice button and a failed-reply warning icon. Alert Ink (#8a1525) is error text.
- Done Green (#1f8a4c) marks a finished guide step. Unseen Grey (#8a96a3) is the resting rating thumbs.

Alert Ink, Done Green, Unseen Grey and Dot Grey are the agent's own additions. Every other value above is copied from ZANY's stylesheet under the same name.

**The ZANY Source Rule.** A new colour comes from ZANY's stylesheet under ZANY's name. Add an agent-only value only for a state ZANY has no colour for, and name it for that state.

**The Magenta Is Help Rule.** Reader Magenta appears on the Help button and nowhere else.

## Typography

Open Sans is the only family on screen, loaded at 400, 600, 700 and 800. It is a brand commitment, since ZANY and VEXcode VR both use it. A system monospace appears only on the researcher page, for prompts and raw model output.

The character comes from weight. Titles and labels sit at 800, names and states at 600 to 700, and only running text sits at 400.

### Hierarchy
- The title role (700, 19px) is the mixed-case title of the check-in note, like the title of ZANY's playground window.
- The headline role (800, 16px, 0.01em tracking) is "INVITE Agent" in the title bar. The first-run guide uses the same weight at 17px.
- The body role (400, 14.5px, line height 1.5) is every chat bubble and guide step. Bubbles cap at 86% of the log width.
- The large body role (400 to 600, 15px) is inputs, the sign-in lead and the check-in note's message.
- The label role (800, 13px, 0.06em tracking, uppercase) is the text on gold and magenta buttons.
- The micro role (800, 10.5px, 0.05em tracking, uppercase) is every field label and the ID pill caption. Bar buttons use 10px with 0.03em tracking under their icon, and the edge tab's spine uses 12px with 0.12em tracking.

**The Bold Label Rule.** A label over a field or under an icon is small, 800 weight and uppercase, the way ZANY labels "Student ID". Running sentences are never uppercase.

## Layout

The coding environment fills the whole screen in a frame, and everything the agent draws floats over it. At rest that is the edge tab alone, 40px wide (46px on hover), pinned to the right edge 250px from the bottom. The check-in note opens 52px from the right edge at the same height, up to 340px wide.

The chat window opens beside the tab, about 400px wide, and can be dragged by its title bar and resized from any corner. Its column stacks a 54px title bar, a 52px tool bar, the scrolling log and the composer. The log pads 16px by 14px with a 12px gap between turns. Student turns sit right, agent turns sit left.

Spacing runs on 4, 8, 12, 16 and 18px, with 10px and 14px for padding inside small boxes. Controls are 44px tall wherever a student taps them.

Under 672px wide the chat becomes a sheet along the bottom, full width, up to 78% of the screen tall, with 10px top corners. The open tab hides there, and with the tutor shown the title bar leaves 80px on the left for the tutor's head. Under 720px tall, as on a Chromebook, the tab and note drop to 100px from the bottom to stay clear of the playground's camera buttons.

## Elevation & Depth

Depth is ZANY's. Windows lift off the coding environment with one soft two-layer shadow, and buttons carry a bevel inside their own edge. Nothing else casts a shadow.

### Shadow Vocabulary
- The window shadow (`box-shadow: 0 14px 34px rgb(15 23 42 / 0.3), 0 3px 8px rgb(15 23 42 / 0.2)`) lifts the chat window, and the check-in note. It is ZANY's `.win` shadow.
- The bevel (`box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.28), inset 0 -3px 0 rgb(0 0 0 / 0.18)`) sits on gold and magenta buttons. A chosen picker half and a block-name chip carry the bottom edge alone.
- The press (`box-shadow: inset 0 2px 3px rgb(0 0 0 / 0.25)`) replaces the bevel while a button is held, with a 1px drop.
- The tile lift (`box-shadow: 0 1px 2px rgb(20 50 100 / 0.18)`) sits under white square buttons in the tool bar.
- The tab shadow (`box-shadow: -3px 4px 14px rgb(20 50 100 / 0.3)`) lifts the edge tab off the screen edge. Open, the tab trades it for an inset shadow, as if pressed into the edge.

**The Pressed In Rule.** A pressed or open control sinks. It turns deep blue or darker gold and takes an inset shadow. It never lifts or glows.

## Shapes

Corners are small and consistent. Windows, buttons, inputs and picker groups use 6px, and pills, notices, square buttons and collapsible sections use 8px. Chat bubbles round to 14px, with the bottom corner on the speaker's side cut to 4px. Starter questions, the count badge and progress bars are full pills. The edge tab rounds only its two left corners (10px), so it reads as part of the screen edge.

Borders are thin and cool. Inputs and starter questions use 1.5px Soft Edge, and dividers use 1px Line. The two-way picker is one rounded box split by a dark rule, the way ZANY draws its level picker.

## Components

### Buttons
The gold button is the one primary action, a bevelled gold slab with dark uppercase text, 44px tall, 18px side padding and 6px corners. Hover brightens it by 8%, press drops it 1px and swaps the bevel for the inset press, and disabled fades it to half. A square version (44px) holds the send arrow beside the composer.

The Help button is the same shape in Reader Magenta with white text, 36px tall, always in the tool bar's left end.

Bar buttons put an icon over a 10px uppercase label, white on the blue title bar and Blue Text on the light tool bar, with a white wash on hover. Square buttons in the tool bar are 34px white tiles with a blue icon that turn deep blue when pressed. Text buttons are bold Focus Blue words with a Blue Wash hover.

### Chips
A block named in a reply is drawn as a VEX block, a VEX Blue chip with white bold text and a bevelled bottom edge. Inside a student's own bubble it turns into a translucent white outline.

Starter questions are white pills with a Soft Edge border and Blue Text. Hover turns the border VEX Blue and fills them with Blue Wash.

### Cards / Containers
Every container is a window. A white body with 6px corners and the window shadow sits under a coloured title bar, VEX Blue for the chat, Window Gold for a check-in. Cloudflare's bot check is left as Cloudflare draws it, alone on a plain white page. Notices are 8px boxes with a 1px border, Blue Wash for information, Cream for a warning and pale red for an error, each with an icon on the left.

### Inputs / Fields
Inputs are white, 44px tall, with a 1.5px Soft Edge border and 6px corners. Focus turns the border Focus Blue and adds a 1px outline, so the edge reads as 2.5px. Each field has a micro label above it and optional 12px help text below.

### Navigation
The title bar holds the agent's name, the student's ID pill (Deep VEX Blue, an uppercase caption over the bold ID), Sign out and Hide. The tool bar holds Help on the left and the Mute and Tutor toggles on the right. Dragging the title bar moves the window, and the cursor shows a grab hand.

### Edge Tab
The agent's resting form. A 40px VEX Blue tab on the right edge carries a chevron or chat icon and the uppercase word "Agent" running down it. Hover widens it to 46px. An unread check-in adds an Alert Red count badge with a white ring on its top-left corner. Open, it turns Deep VEX Blue with an inset shadow.

### Check-in Note
A check-in that arrives while the chat is tucked away. A small window with Window Gold's title bar and a mixed-case "Checking in" title slides out of the tab, clipping open from its right edge over 420ms. It holds the message in 15px text, a gold Reply button and a Later text button. This slide is the page's one authored motion. The chat window itself opens with a quick 260ms fade and scale from the tab's side, and reduced-motion settings turn off both.

### Chat Turns
Student turns are Focus Blue bubbles with white text on the right. Agent turns are Grey Wash bubbles with a Line border on the left, followed by thumbs to rate them. A check-in turn is Cream with a gold-edged border and a small uppercase Gold Edge label naming it. A failed turn is pale red with a warning icon. While the agent is thinking, three VEX Blue dots hop in its bubble.

## Do's and Don'ts

### Do:
- Take every colour from ZANY's stylesheet under ZANY's name before adding one of the agent's own.
- Give every window a coloured title bar, 6px corners and the window shadow (`0 14px 34px rgb(15 23 42 / 0.3), 0 3px 8px rgb(15 23 42 / 0.2)`).
- Make the main action a gold bevelled button with 13px uppercase 800 text and a 44px height.
- Label fields with the 10.5px uppercase 800 micro label.
- Keep primary buttons and fields 44px tall.
- Turn off the slide, the window open and every looping animation under reduced motion.

### Don't:
- Don't use any family but Open Sans outside the researcher page's monospace.
- Don't use Reader Magenta for anything but Help.
- Don't add a glow, a gradient fill or a lifted hover to a button. Hover brightens or washes, and press sinks.
- Don't let the agent cover the student's code at rest. It waits at the edge until opened.
