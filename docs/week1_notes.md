# Week 1 notes: OpenGL → my hardware

Fill one row per LearnOpenGL chapter. The goal is not OpenGL itself,
it is knowing exactly which hardware block each idea becomes.

| Chapter | What OpenGL does | Which of my modules does this | Number format / width it needs | Open questions |
|---|---|---|---|---|
| Hello Window | | (none, host side) | | |
| Hello Triangle | | | | |
| Shaders | | | | |
| Transformations | | vertex_transform.sv | | |
| Coordinate Systems | | vertex_transform.sv + persp_divide.sv | | |

## Things I must decide by the end of Week 1
- [ ] Are Q16.16 / Q2.14 / Q12.4 enough? (write the largest value I expect for each)
- [ ] Matrix order: I send row-major. Does my OpenGL reference use column-major? (glm does!)
- [ ] Depth: 0 = near in my spec. OpenGL's default depth range? How do I map it?
- [ ] Which board display port / PL clock / LED pins does my ALINX board have?
