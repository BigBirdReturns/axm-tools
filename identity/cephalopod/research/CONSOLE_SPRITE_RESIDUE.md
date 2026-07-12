# Console sprite residue for the cephalopod icon

**Status:** design research, not canonical source  
**Captured:** 2026-07-12  
**Target:** a 24–32 px square cephalopod icon whose coherent organism occupies the left and center while unstable sand on the right undergoes ordered console-style failure.

## Source boundary

This record preserves transferable construction logic rather than franchise artwork. Full commercial sprite sheets are not mirrored. The repository stores the source URLs, page metadata, and original analysis below. One 256 × 224 *SimCity* debug-screen capture is retained locally because it is the precise visual evidence for the corruption mechanism under study. It remains a research reference and cannot become source material for the icon.

The Spriters Resource is useful here as an observational archive rather than a style authority. Its SNES, Genesis, and GBA collections contain incompatible studios, genres, palettes, and character languages. The transferable residue is the way low-resolution assets preserve silhouette, negative space, modular assembly, palette roles, and frame economy under platform constraints.

## Sources observed

| Source | Research use | Page metadata observed on 2026-07-12 |
|---|---|---|
| [SNES index, S](https://www.spriters-resource.com/snes/S.html) | Platform browse context and access to *SimCity* | SNES index reported 3,855 assets and 168 games in the S section view. |
| [SimCity, SNES](https://www.spriters-resource.com/snes/simcity/) | UI, icon, text, terrain, and screen-layer reference inventory | Page reported 26 assets across buildings and miscellaneous screens. |
| [Launch Octopus, Mega Man X](https://www.spriters-resource.com/snes/mmx/asset/3126/) | Segmented limb readability across poses; negative reference for franchise-specific anatomy | 715 × 649 GIF, 52.48 KB; submitted credit shown as Freedom Fighter. |
| [Sega Genesis index](https://www.spriters-resource.com/sega_genesis/) | Platform browse context; palette and cell-based sprite observation | Index reported 5,628 assets and 583 games. |
| [Badniks, Sonic the Hedgehog 2](https://www.spriters-resource.com/sega_genesis/sonicth2/asset/10398/) | Multi-enemy sheet showing concise silhouettes and object assembly; negative reference for robotic character language | 1036 × 1240 PNG, 97.38 KB; uploaded by Paraemon. |
| [Game Boy Advance index](https://www.spriters-resource.com/game_boy_advance/) | Platform browse context and reduction comparison | Index reported 14,111 assets and 1,214 games. |
| [Octopus (Classic), Game & Watch Gallery 4](https://www.spriters-resource.com/game_boy_advance/gnwgal4/asset/21287/) | Strong figure-ground separation and limb recognition with minimal internal texture | 565 × 547 PNG, 35.25 KB; uploaded by Eddo. |
| [SimCity SFC debug capture](https://retro-v.games/wp-content/uploads/2024/02/sfc-simcity-debug.png) | Direct evidence for ordered layer collision rather than generic “glitch art” | Mirrored at `references/simcity-sfc-debug.png`; 256 × 224 indexed PNG; SHA-256 `14faab639526ce45d662a0675ad5b6f83a76e11a1bdadd7dbebff1de38534a59`. |

## The residue

### Corruption is a construction failure, not a post-processing effect

The *SimCity* debug screen is uncanny because several internally orderly systems coexist on one rigid screen: a blue field, a residual moon-and-star graphic, a bordered Japanese message box, and a monospaced debug register list. Nothing dissolves into random particles. The visual failure is legible as misplaced, retained, or overlaid modules. For the cephalopod icon, the right-side sand should therefore fail through grid-aligned displacement, duplication, substitution, omission, palette reassignment, or layer overwrite.

The acceptable vocabulary is narrow. A sand row may shift horizontally while retaining its internal pattern. A substrate tile may duplicate at a new height and become a ledge. A missing tile may create an aperture. A wrong tile may interrupt one terrain band while another continues behind it. A palette index may recolor one rectangular block. A background strip may coexist with a second terrain state. Generic scanlines, motion streaks, square-particle clouds, and whole-image smearing do not express this mechanism.

### The organism remains coherent while the terrain fails

The mantle and central body preserve organism-level intent. They must remain continuous and readable on the left or left-center of the square. Corruption belongs primarily to the sand and environmental field on the right. An arm may enter the corrupted region, but its route must remain anatomically connected to the body. The icon should show adaptation to damaged terrain rather than damage to the animal.

The causal test is explicit: every disrupted terrain state must create at least one additional useful route, brace, opening, ledge, redirect, or contact point. If a shifted tile merely decorates the right edge, it is noise. If it lets an arm cross, grip, emerge, or redirect, it carries the anti-fragile argument.

### Silhouette and negative space carry the small states

The classic GBA octopus reference demonstrates that a low-resolution cephalopod remains legible when the body is a unified mass and the arms are separated by deliberate negative space. The relevant inheritance is not its character silhouette. It is the economy by which each limb path remains distinguishable without suction cups, texture, or expressive facial detail.

At 32 × 32, the design may support four to six readable arm routes and three to five distinct contacts. At 16 × 16, the body mass, asymmetry, two or three arm routes, and right-side terrain failure must survive. At 12 × 12, approximate recognition is sufficient, but the state must be hand-resolved. It cannot be a mechanically shrunken 32 × 32 drawing.

### Arm topology communicates distributed intelligence

Different arms must perform different local operations. One may brace downward into stable substrate. One may probe upward. One may cross an aperture. One may curl around a duplicated ledge. One may reappear through an opening. Repetition of the same ornamental curl does not communicate local autonomy. The arm routes should vary in direction, bend count, height, and contact type while remaining visibly part of one organism.

The Launch Octopus and Sonic enemy sheets are negative as well as positive evidence. Their readable segmentation and pose economy are useful. Their franchise anatomy, robotic components, weapon coding, character expression, and established silhouettes are prohibited inheritance. No external game character may become the drawing source.

### Palette is functional and interpretive

The photograph supplies value hierarchy, atmospheric separation, material contrast, and a warm-versus-cool tension. It does not require beige flesh, brown sand, and cyan eyes. Each proof sheet should test a different three- or four-color console reduction whose colors have roles: organism light, organism or substrate midtone, dark field, and optional fault or sensor accent.

Suitable exploratory families include cobalt with sulfur and bone; deep teal with ivory and oxidized orange; near-black with olive, cream, and cold mint; or dark plum with pale green-gold and ember. These are hypotheses, not frozen tokens. The selected palette must still produce a clear organism/substrate boundary and preserve the right-side corruption at 16 × 16.

### Hardware scale is translated, not imitated literally

Literal 8 × 8 hardware tiles would consume too much of a 24–32 px icon. The visual analogy should therefore use a small number of 3 × 3, 4 × 4, or irregular but grid-aligned macro-blocks. The enlarged proof view must be an exact nearest-neighbor enlargement of the native bitmap, with hard edges and no anti-aliasing.

## Four proof sheets, four candidates each

Each sheet contains one control candidate and three candidates derived from the current understanding. The control may preserve the strongest prior direction. The remaining candidates must differ in mechanism, not only posture or glitch density.

### Sheet 1: organism topology

1. **Control:** strongest prior left-weighted octopus, corrected only enough to keep corruption in the terrain.  
2. **Anchor plus emergence:** low planted mantle; broad front contacts; one arm exits through a right-side aperture.  
3. **Anchor plus distributed action:** smaller mantle; several arms perform distinct probe, brace, grip, and redirect operations.  
4. **Distributed emergence:** body partly obscured on the left; coherent arms reappear through separate right-side openings.

Corruption is held relatively constant so the topology can be compared.

### Sheet 2: terrain failure grammar

1. **Row displacement:** one or two sand bands shift horizontally and become new braces.  
2. **Tile duplication:** repeated terrain chunks form a climbable or grippable ledge.  
3. **Missing-tile apertures:** rectangular absences create passages through which arms remain connected.  
4. **Palette or layer overwrite:** an ordered second terrain state occupies part of the right side and changes available contact geometry.

The organism is held relatively constant so the failure mechanism can be compared.

### Sheet 3: organism-to-failure coupling

1. **Bridge:** an arm spans from stable sand to a duplicated tile shelf.  
2. **Split route:** two arms exploit two different apertures.  
3. **Brace and redirect:** a displaced row receives pressure and changes an arm’s trajectory.  
4. **Re-emergence:** the body remains buried or obscured while arms appear through multiple corrupted openings.

Every candidate must make the gain in capability visible.

### Sheet 4: integrated Venn extremes

1. **Anchor dominant:** greatest central mass and physical control, least corruption.  
2. **Substrate dominant:** lowest visible body, strongest emergence through terrain.  
3. **Distributed intelligence dominant:** smallest coherent mantle and widest diversity of local arm actions.  
4. **Reroute dominant:** most extensive right-side tile failure that still preserves one coherent organism and readable small state.

The four candidates should also test genuinely different nonliteral palette families.

## Acceptance tests

A candidate passes only when the native 32 × 32 map shows a coherent, left-weighted cephalopod gaining at least one useful route, contact, brace, opening, or redirect because the right-side substrate has suffered an orderly console-style failure. The mantle cannot be fragmented. The terrain failure cannot be a particle cloud. The face is limited to zero, one, or two sensor pixels. The icon uses three or four colors, hard bitmap edges, no gradients, no anti-aliasing, and no faux-vector smoothing.

The 24 × 24, 16 × 16, and 12 × 12 states are separate hand-resolved maps. Display enlargements use integer nearest-neighbor scaling. A candidate that only reads in an enlarged illustration has failed the platform test.

## Provenance consequence

No referenced sprite, screenshot, game asset, prior generated proof, or external character is a canonical source. Any selected cephalopod must be reconstructed as an original map from the photograph, this design logic, and direct pixel decisions. The frozen source will require a map, palette tokens, export code, release manifest, and custody law separate from the SCG dandelion constitution.
