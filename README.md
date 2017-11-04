# UniCog: Unified Cognitive Assessment Platform (2015-17)

Since April 2015, I have been developing a collection of serious mobile (Android) games, sharing a common back end, for the assessment and intervention of visuomotor and mental health conditions. To date, we have developed the followed games:

- A star-cancelation game, inspired by the star-cancellation test - http://www.strokengine.ca/assess/sct/; in this game, any background can be used, with objects familiar (and/or engaging) to the patients, and the application implements the test- scoring rules.
- A clock-drawing game, inspired by http://www.strokengine.ca/assess/cdt/
- A number of variants of a whack-a- mole game, developed using PhyDSL, our model-driven app-construction engine; the most complex of these variants, includes multiple difficulty levels (with a therapist defining the rules for transitioning between them) and records data on the patient’s reaction time, accuracy and attention.

UniCog is a web-based backend that centralizes the collection of information coming from all of our digital assessment and intervention tools. It provides a unified API in order to query and explore the scoring metrics produced by each of our serious games, and other digital assessment tools. This repository contains the codebases of UniCog's back end developed using Python/Flask and Javascript.

You can find comprenhensive API documentation and deployment instructions in the  api-specification-v1 and dev-manual pdfs in the root of the repository. 

Note: this project was originally called UCAP but has since then been renamed UniCog.
