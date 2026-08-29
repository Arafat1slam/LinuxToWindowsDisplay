# License

**Recommendation: MIT.**

A quick note on why, since you asked for a suggestion between MIT and GPL-3.0:

- **MIT** is maximally permissive — anyone can use, modify, and redistribute ScreenLink, including inside proprietary or commercial software, as long as they keep the copyright notice. This maximizes adoption and makes it easy for other projects (or even a commercial fork) to build on your work, which is usually the right call for a utility/tool project where your goal is for people to *use* it, not to control what downstream projects do with it.
- **GPL-3.0** is "copyleft" — anyone who distributes a modified version must also open-source their changes under GPL-3.0. This is the right choice if your priority is ensuring the project (and all its derivatives) stays open-source forever, even at the cost of some companies/projects declining to use it because of that requirement.

For a Spacedesk-style personal utility aimed at broad adoption and easy contribution, **MIT is the more common and generally recommended choice** — it's what most comparable open-source LAN-streaming tools use. If keeping all downstream forks open-source matters more to you than maximizing adoption, swap the text below for the [GPL-3.0 text](https://www.gnu.org/licenses/gpl-3.0.txt) instead — that's a one-file swap, not an architectural decision, so it's safe to change your mind on later.

To use this file as-is: rename it to `LICENSE` (no extension) to match GitHub's convention for automatic license detection, and fill in the year and name/organization below.

---

```
MIT License

Copyright (c) 2026 <ARIS>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
