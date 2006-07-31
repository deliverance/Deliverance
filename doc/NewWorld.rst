============================================================
NewWorld Template Machinery
============================================================
------------------------------------------------------------
Analysis of current skinning and proposal for a new approach
------------------------------------------------------------


Plone has accumulated a baroque stack of templating and skinning
approaches with plans for adding more.

This document analyzes the current issues and makes recommendations
with working code for new approaches.  The specific focus is on how
the UI consultant and the component consultant accomplish their jobs
both individually and together, and throughout a project.


Caveat
------

ZPT started with a core vision: improve workflow by letting HTML/XHTML
authors work with their tools.  If you don't care about this vision,
and think ZPT is for developers, then you won't care about this
proposal.


Summary
-------

  o The UI consultant's job needs to become more productive, more
  joyful

  o Plone needs a distinct, formal concept of themes


Glossary
--------

  o UI consulting.  At a minimum, drawing pixels on browser screens.
  Beyond that, collecting what needs to be done (computations,
  business rules) as stubs to be completed by the component team.

  o Theme.  The corporate identity artifacts.  HTML, CSS, JS, PNG. No
  templating, no programming.

  o OldWorld. ZPT, skins, view classes, FS templates and TTW stuff.

  o NewWorld. This proposal.

  o o-wrap template. The current approach to corporate id.
  ``main_template.pt``, which provides stuff that gets pulled into
  ``folder_contents.pt`` during evaluation.

  o Main template.  o-wrap.

  o Context template. ``folder_contents.pt`` etc.

  o Dreamweaverish.  A placeholder for any authoring tool, WYSIWYG or not,
  that structurally processes XHTML and thus increases
  productivity/quality.


The Problem
-----------

Instead of leading off with a long-winded architecture discussion,
let's just jump right into specific instances of problems.  These are
issues Plone inherits from its Zope/CMF/AT/Plone stack.

Here we go with a top-ten list of annoyances:

1. Getting a consistent DOCTYPE.

Our first example is small in scope but wonderfully illustrative of
the challenge.

Correct DOCTYPEs are critical to UI, as IE will trigger quirks mode
unless all the pages in your site have the correct DOCTYPE.  This
applies to any potential add-ons written by others.

Like other Zope 2/3 systems, Plone's ZPTs have a challenge on this::

  <metal:page define-macro="master"><metal:doctype define-slot="doctype"><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"></metal:doctype>
  <metal:block define-slot="top_slot" />

This is the top of `main_template.pt`, the "o-wrap" for Plone.  When a
UI designer wants to structural change the look-and-feel of a Plone
site, this template is their starting point.  ZPTs original goal was
to look like normal HTML, and this certainly doesn't.

Getting some static text at the top of each template is seemingly a
small use case.  However, the architecture of ZPT makes this into a
challenge with negative consequences on the subtemplates (e.g. you
can't define top-level variables that influence the global macro.)

Summary: DOCTYPEs are important.  Controlling them turns templates
into something unusable by UI consultants.


2. Validation.

The previous problem was a small detail with large consequences.  This
problem is larger in scale and philosophy.

ZPTs original goal was simple: "Well-formed markup to please
Dreamweaverish."  There's a flaw in this, though.

DOCTYPEs tell parsers what language you are speaking.  Externally,
they tell the browser what grammar to use.  Internally, they tell the
UI consultant's editor what tool to use.

ZPT uses the same file artifact for both purposes.  When the ZPT is
rendered, the non-valid XHTML markup is processed and removed.  The
result fulfills the contract of the DOCTYPE for external use.

However, when Dreamweaverish opens the file, it sees a DOCTYPE for XHTML,
then a bunch of tal: and metal: stuff that violates that markup.  When
the UI consultant presses the "Validate" button, a hundred errors are
produced.  Worst case, the tool's helpful features (autocomplete,
etc.) get turned off due to non-conformance.

What are the choices?

  a. Decide validation and tools don't matter and make UI consultants
  use vi. [wink]

  b. Make a new DTD or XSD/RNG that includes the tal and metal
  namespaces.  Unfortunately, this new declaration gets sent merrily
  back to the browser, thus breaking the external contract.

  c. Formally split the external stage of processing from the
  internal.

This proposal will describe (c).

Ultimately, Plone needs to take a stance on the original ZPT premise.
Does Plone advertise that templates should be usable in HTML tools
when opened directly from disk?  If so, the current situation is
unacceptible.  If not, then the productivity of UI consultants is
going to be trial-and-error, reload-Zope-and-view.

Summary: Validation is key to improving the quality and productivity
of the UI consultant.  It is also an important part of UI consultant's
tools.  The current processing approach conflates external validation
and internal validation.  Split them.


3. link and script in head.

Systems like Plone have some site-wide resources (CSS and JS) that get
referenced by every page.  These references are done by `<link>` and
`<script>` elements in the `<head>`.

Some pages have per-page needs for CSS and JS.  This is problematic.
It requires a new block-level element in the context template, usually
something like `<metal:block fill-slot="top_slot">`.  The average UI
consultant, when confronted with this, will:

  a. Wonder what in the world is a metal block.

  b. Wonder why it is appearing in the head.

  c. Get aggravated when the HTML page is no longer valid and none of
  the CSS and JS is included when viewed from disk.

This is worse for second-order macros like Kupu, that have to fill the
slot of a slot.

Summary: It is wrong to use in-page, non-HTML constructs to push
markup from the context template to the o-wrap template.


4. Corporate identity.

I've written about this before for the Zope Site Themes.  I won't make
the case again, but I'll describe the solution below.

  http://www.zope.org/Wikis/DevSite/Projects/ComponentArchitecture/SiteThemes

5. Macros and slots.

Quick, what is the set of macros used in CMF?  Plone?  Zope 3?  What
slots are available?  What custom macros and slots do you have in your
consulting project?

Zope 3 brought "explicit is better than implicit" to software.  The UI
side needs the same thing.  But we need ideas on how to avoid
activities that feel like programming on the UI consulting side, but
yield the benefits of knowing what is needed and what is available.

Additionally, the connection between the o-wrap and context template
is too hard-wired, making things brittle.  Just like adapters prevent
changes in one side from affecting the other, we need similar ideas.

6. Customize button.

The CMF skin system was originally designed to let UI consultants
customize the UI without touching the artifacts they got from the
"system".  Great idea, but with consequences:

  o If you make a one-line markup change ``folder_contents.pt``, you
  own it.  Any updates in the system's template won't be seen.

  o Zope 3 might make this go away.


7. Tedious instructions.

In CMF/Plone templates, every `link`, `script`, `a`, `img`, etc.  As
such, each of these gets a `tal:attributes="src:
{portal_url}/foo.png"` added to it, even though the image src was
stated on the actual src attribute.

What happens?  First, nobody even bothers putting an actual src
attribute, meaning the original premise of ZPT is thrown out the
window.  Second, the poor UI designer is confronted with this weird
construct and has to remember, from system to system, whether it is
`portal_url` or some other magic chant.

This is painful.  More importantly, it tosses out the original premise
of ZPT, which then tosses out Dreamweaverish and the
productivity/quality gains.

Most importantly, this is just one example of a recurring problem:
Zope's template processing model doesn't really parse markup.  It
does, but internally as a black box that can't be influenced.

What's needed is a processing model where the job of fixing portal
URLs, *and similar jobs*, is moved out of the template, but is still
controlled by the integrators.

Summary: Rewriting attributes and similar constructs breaks
productivity and highlights a recurring problem.

8. Template metadata "resource forks".

Since ZPTs aren't treated as documents, you can't put metadata in them
for use in Zope/CMF.  To add metadata, developers have to manage a
separate ".metadata" file.

9. Cleanup.

Let's say you wanted to cleanup the markup produced on your site.
Perhaps the UI consultant wants to:

  o Ensure common look, as described under "Corporate identity" above.

  o Compress page size by removing space.

  o Improve readability by indentation.

  o Produce valid XHTML.

The current templating system doesn't provide a place in the
processing to intervene and take such action.

10. Reload.

In debug mode, template changes don't require a reload.  That's great!
Except the official new way is to move all logic to a view class, and
that doesn't get reloaded.  Add a new image via ZCML?  Reload.

Such interruptions in "flow" are anathema in the new realm of agile
frameworks.


Values
------

Now that we have a list of headaches, let's step back and talk about
the kinds of values that we want to accomplish for UI consulting in
the future.

1) Plone consulting should be UI driven.

I think most would nod their head patriotically for such a statement.
But the reality really isn't like this.  Most Plone consultant
projects are component-driven.

If we say this, let's talk about the environment used by UI consulting
vs. component consulting.  The latter is moving towards testing,
validation, doctests, etc.  The former is still a hit-or-miss,
low-quality environment.  If the former is doing the driving...well,
we want the driver to have the best quality if we hope to avoid
accidents.

We should analyze this claim.  And we should make sure that the
highest value, beyond all others, is to make Plone projects driven by
UI consulting.  Then, when we evaluate the headaches listed above, we
simply choose not to accept reasons why the headaches must continue.

Why do we want this?  The customer wants the UI.  They don't want the
components.  Also, the UI consultants are better with customers.  When
a business rule is captured in the "software", it should be expressed
in artifacts used by UI consultants and *not* forked into new
artifacts used by the component team.

Finally, back to hijacking.  When the consultants "collaborate" with
the UI team currently, the result is usually a mess:

  - The ZPTs become unusable for Dreamweaverish nor browser preview.

  - The templates are only meaningful when evaluated by the server,
    meaning restarts, software dependencies, etc.

  - When stuff breaks on the "trunk", the UI consultants are stuck.

2) Quality.

Let's make quality a part of UI consulting.  How can we work in a
deliberate way and know about the quality of our UI work?

3) Joy.

The UI consultants have a job to do.  They are good at it and have a
way to do it.  Let them do the work with fun and joy.  A baroque pile
of "you just gotta figure it out" technologies is not joy.

4) Flow.

Other web frameworks talk about "flow": no interruptions, no alarms,
no surprises.  Stuff makes sense.  Refactoring is fun.  You know where
to find things.  Can Plone do better on this?


Proposal
--------

We should continue talking about the kinds of things that drive UI
consultants crazy.  Ways that we can move ahead of the competition.

But we can also brainstorm ideas -- simple ones, wild ones -- that
might improve things.  Maybe the wild ones will inspire the final
ones.

1) Themes.

The Site Themes proposal (and related work) goes into detail on this.
Plone 3 *must* split the corporate id part (themes) from the dynamic
generation part (skins or templates).

  o When you make a Plone site look like your own, you shouldn't touch
  the same artifacts as the "software".

  o You shouldn't see anything that looks like software
  (metal:define-slot etc.)

  o Your artifacts should still be well-formed and *valid* in both
  your editor and browser

...and a host of other reasons defined in the Site Thems URL:

    http://www.zope.org/Wikis/DevSite/Projects/ComponentArchitecture/SiteThemes

How might this work in practice?

a. Save a pile of XHTML, CSS, JS, PNG to disk.

b. Edit a rule file that tells Plone how to fill in boxes with dynamic
stuff.

c. Nothing in your HTML changes.

d. The output of the ZPT etc. is the input to the theme.

e. There are no macros or slots used to setup DOCTYPEs or specify
which boxes to fill.

f. You can run a 100 line command-line script to do the merging.  (Or
a CGI script, or lots of other things.)

g. You can analyze your pile of context templates to see if they have
the identifiers needed for filling in boxes.

h. If something breaks, the template still renders, but without the
broken box getting filled.

i. Dreamweaver, nxml-mode, etc. can still validate your corporate id.

j. We can use off-the-shelf parsers etc. to implement the connection
between context output and theme input.

k. We don't have matching macro/slot declarations on each side that
are easy to break.  The rule file controls what matches with what
(probably with XPath).

l. Based on the previous point, refactoring becomes fun again.

m. The component people rejoice because their templates no longer have
any connection to styling.  No slot filling, etc.


2) New approaches to templating.

Although I have code for the former, I'm still in progress on the
following sections.  Since that makes it science fiction, I will
provided bullets with "imagine if"-style explanations.

a. Meaningful error messages.  Imagine that, as you worked on your UI
consulting, mistakes (yours or others) produced useful error messages.
Even better, imagine that you felt you could jump in and isolate the
error.  Egads, even fix it.

Also, imagine if the "system" was isolated from your part.  You know
what "the system" is supposed to hand you.  You can prove if "the
system" did or didn't, and thus, whether the problem is in the UI
consulting layer.

b. Meaningful templates. Imagine if the information in the template
could be used by the system.  For example, a ``<link rel="next"
href="foo.html"/>`` could be used by the view class or other parts of
the processing chain.

This point has a LOT of potential.  Once the template becomes a useful
artifact, rather than tag soup parsed into a "proprietary" parse
format, we can let the system's templates (written by competent
component consultants) encode more meaning.

c. What drew the pixel?  Imagine you could look at a rendered, dynamic
page, and could find out what "instructions" were responsible for each
pixel.  That alone would make NewWorld discussions worthwhile.

d. Output hacking.  Imagine if you could affect every ``<a href="">``
on the site and, in certain conditions, modify it.  Wouldn't that be
great?  Imagine if you could add tag information to the output without
even *touching* a single "system" artifact, such as a ZPT?

e. Tool support.  Imagine if your template language had a schema.  You
could use nxml-mode, oXygen, Dreamweaver, or a host of other tools
that know how to tell if you screwed up your template.  Wouldn't that
be better than visiting the browser, pressing reload, and deciphering
a ZPT message?

Really, this point is colossal.  People are long used to the benefits
that smart code editors provide.  They provide vast improvements in
both productivity and quality.  They can even help assist you in
knowing what is possible in the context of something else -- even
providing tooltips to explain choices.

Beyond that, we can write tests and other tools that process the site
and see what's going on.

f. Push templates. (Courtesy of Tres.)  Imagine a system where a
template doesn't pull information in by knowing the intricasies of the
catalog API.  Instead, the view class prepares everything that is
available and pushes it into the template.

With this, the UI consultant could actually master some the Python
code to assemble static Python dictionaries to be replaced later by
the component consultants.

g. Testing.  Imagine the ongoing process of UI consulting was
testable.  Imagine that, while working on the templates and
presentation logic, the UI consulting could leave some droppings that
let made the UI testable.  Imagine this was done in a very natural
way, from the perspective of the UI consultant.  It fits their brain,
so they do it.

h. Documentation.  Imagine the same thing were true for documentation.
UI consultants deal with customers.  Customers like to know what is
finished, in progress, and just started.  They like to know how the UI
plugs together, what is the intent, etc.

Components have lots of stuff now for this.  UI consultants have
squat.  They generally draw boxes in Illustrator upfront, then
immediately forget about it, as they become out-of-date.

i. Business rules.  Imagine the UI consultant gets to "own" the
conversation with the customer about business rules.  Archetypes
provides schemas that express constraints in a reasonably-friendly
fashion.  What more can be done like this, and how can this be done
more in the UI consultant's domain?

Why is this worth discussing?  Because the UI consultant is a better
fit for managing this:

  o Customers like pixels, not code

  o UI consultants are usually more cuddly than component developers

j. Optimization hints.  Imagine a templating model that could say,
"This block doesn't change much."  For example, only on restart.  Or
only when another thing changed.  Or etc.  Currently this is done by
cache managers, that feel more like code.  Let the UI consultant talk
it over with the customer and leave hints in the templates.

*Note: This is a benefit of splitting out themes from templates.  We
 can then make templates into more of a domain-specific language for
 UI consulting without freaking out the Dreamweaver-ish people.*

k. Forms and validation.  Long discussion, ask Doug Winter.


3) Serverless UI consulting.

I'm working on a desktop tool that lets you do server-ish things
without a server.  If it pans out, it has a number of interesting
possibilities for automating the business of UI consulting, while
removing many of the headaches.

a. Reload sucks.  Imagine you didn't have to do server restarts for
anything related to UI consulting.  But the artifacts you created were
still used by the component consultants (though not hijacked).

b. Freedom.  Imagine you could develop a UI without caring about
breakage by the component folks.  Without even installing a Zope.  You
could sit in front of the customer, do work, and see 0.05 second
response time without restarts.

c. Validation.  Imagine a GUI that tells you when things need fixing.
That's the beauty of validation and standards.  We can have a schema
for all inputs, intermediary steps, and outputs of UI consulting.  We
can even look at CSS rules, theme rule files, configure.zcml files,
and more.

d. Refactoring.  Want to change a "slot" from foo to bar?  Tell the
tool and it will fix all the artifacts in your site.  Want to change a
CSS class name?  Ditto.  Rename a template?  Find orphaned templates
or images?

e. Issue tracking.  Lots of code editors support leaving XXX comments,
then seeing a list of what needs to be done.  ZPT?  Forget about it.
Imagine you could do this in UI consulting.

o lint-style stuff

  - is input page well-formed? output?

  - valid?

  - where do boxes come from?

  - any templates/resource not in ZCML?

  - vice versa?

  - list all macros/slots/exports in the site, w/ frequency counts

  - list all classes/ids in the site
