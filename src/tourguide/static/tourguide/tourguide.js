/*
 * django-tourguide: fetches a tour spec from the server and drives driver.js with it.
 *
 * The interesting part is that a tour can span pages. The server holds the position, so the
 * adapter can record where the user got to, navigate, and pick the tour up again on the next
 * page. That is also why progress is not kept in sessionStorage: a tour survives a reload, a
 * new tab, and a different browser.
 *
 * Nothing here knows anything about driver.js beyond this file. The server emits a plain JSON
 * spec, so a different renderer means rewriting this adapter and nothing else.
 */
(function () {
  "use strict";

  var configElement = document.getElementById("tourguide-config");
  if (!configElement) {
    // The page did not load the tour guide. Not an error: {% tourguide %} is per page.
    return;
  }

  var config = JSON.parse(configElement.textContent);
  var driverFactory = window.driver && window.driver.js && window.driver.js.driver;
  if (!driverFactory) {
    console.warn("django-tourguide: driver.js did not load, so no tour can run.");
    return;
  }

  /* ---------------------------------------------------------------- server ---- */

  function endpoint(template, slug) {
    return template.replace(config.slugPlaceholder, encodeURIComponent(slug));
  }

  function getJSON(url) {
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    }).then(function (response) {
      // A refusal is a normal answer here: a tour the user may not see is a 404, and an
      // expired session is a 403. Either way there is nothing to run.
      return response.ok ? response.json() : null;
    });
  }

  function postProgress(slug, payload) {
    return fetch(endpoint(config.endpoints.progress, slug), {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": config.csrfToken
      },
      body: JSON.stringify(payload)
    }).catch(function () {
      // Losing a progress write costs the user their place, not the tour they are in the
      // middle of, so let it fail quietly rather than interrupting them with an error.
    });
  }

  /* ------------------------------------------------------------------ pages ---- */

  function normalisePath(path) {
    if (!path) {
      return path;
    }
    var trimmed = path.replace(/\/+$/, "");
    return trimmed === "" ? "/" : trimmed;
  }

  /**
   * The page each step belongs to, resolved once for the whole tour.
   *
   * A step with no path of its own belongs to whatever page the previous step was on, which
   * is the usual case for consecutive steps. Only the first step in a run names its page, so
   * the value has to be carried forward rather than read per step.
   */
  function resolvePages(steps) {
    var current = null;
    return steps.map(function (step) {
      if (step.path) {
        current = step.path;
      }
      return current;
    });
  }

  function isHere(path) {
    // A null page means "wherever the tour already is", which is always here.
    return path === null || normalisePath(path) === normalisePath(window.location.pathname);
  }

  /* --------------------------------------------------------------- rendering ---- */

  function toDriverStep(step) {
    var popover = {
      title: step.title || "",
      description: step.content || "",
      popoverClass: "tourguide-popover"
    };
    if (step.side) {
      popover.side = step.side;
    }
    if (step.align) {
      popover.align = step.align;
    }

    var element = findElement(step.element);
    // A step whose element is not on the page renders as a centred box rather than failing.
    // That happens legitimately for steps belonging to another page, and also when a host
    // project restyles away the thing a step used to point at.
    return element ? { element: element, popover: popover } : { popover: popover };
  }

  function findElement(selector) {
    if (!selector) {
      return null;
    }
    try {
      return document.querySelector(selector);
    } catch (error) {
      // Selectors are authored in the admin, so an invalid one is a typo rather than a bug.
      // Treat it as a step with no anchor and say so, instead of taking the tour down.
      console.warn("django-tourguide: '" + selector + "' is not a valid CSS selector.");
      return null;
    }
  }

  /* -------------------------------------------------------------------- tour ---- */

  function runTour(spec, startIndex) {
    var pages = resolvePages(spec.steps);
    var completed = false;
    var driverObj = driverFactory({
      showProgress: true,
      allowClose: true,
      steps: spec.steps.map(toDriverStep),
      onNextClick: function () {
        move(1);
      },
      onPrevClick: function () {
        move(-1);
      },
      onDestroyStarted: function () {
        // driver.js calls this both when the user closes the tour and when we end it
        // ourselves, so completion is flagged first to keep the two outcomes apart. They are
        // stored separately, and conflating them would make an abandoned tour look finished.
        if (!completed) {
          postProgress(spec.slug, { action: "dismissed" });
        }
        driverObj.destroy();
      }
    });

    function move(delta) {
      var target = driverObj.getActiveIndex() + delta;
      if (target < 0) {
        return;
      }
      if (target >= spec.steps.length) {
        completed = true;
        postProgress(spec.slug, { action: "completed" });
        driverObj.destroy();
        return;
      }

      var order = spec.steps[target].order;
      if (!isHere(pages[target])) {
        // Record before leaving, and only navigate once it has landed. The next page resumes
        // from the stored position, so a navigation that outran its own write would arrive
        // and put the user back on the step they just left.
        postProgress(spec.slug, { action: "step", step: order }).then(function () {
          window.location.assign(pages[target]);
        });
        return;
      }

      postProgress(spec.slug, { action: "step", step: order });
      if (delta > 0) {
        driverObj.moveNext();
      } else {
        driverObj.movePrevious();
      }
    }

    driverObj.drive(startIndex);
  }

  function indexOfOrder(steps, order) {
    for (var i = 0; i < steps.length; i++) {
      if (steps[i].order === order) {
        return i;
      }
    }
    return -1;
  }

  /* ------------------------------------------------------------------ start ---- */

  function resume(tour) {
    return getJSON(endpoint(config.endpoints.spec, tour.slug)).then(function (spec) {
      if (!spec || !spec.steps.length) {
        return false;
      }
      var index = indexOfOrder(spec.steps, tour.progress.last_step);
      if (index === -1) {
        // The tour was re-imported and no longer has the step this user stopped on. Starting
        // over is better than guessing at a position that no longer means anything.
        index = 0;
      }
      // Only resume where the user actually is. A tour whose next step is on another page
      // waits for them to go there, rather than navigating a page they chose to open.
      if (!isHere(resolvePages(spec.steps)[index])) {
        return false;
      }
      runTour(spec, index);
      return true;
    });
  }

  function begin(tour) {
    return getJSON(endpoint(config.endpoints.spec, tour.slug)).then(function (spec) {
      if (!spec || !spec.steps.length) {
        return false;
      }
      if (!isHere(resolvePages(spec.steps)[0])) {
        return false;
      }
      postProgress(spec.slug, { action: "step", step: spec.steps[0].order });
      runTour(spec, 0);
      return true;
    });
  }

  /** Try each candidate in turn, stopping at the first that starts a tour. */
  function firstThatRuns(candidates, attempt) {
    return candidates.reduce(function (chain, candidate) {
      return chain.then(function (started) {
        return started ? true : attempt(candidate);
      });
    }, Promise.resolve(false));
  }

  function autostart() {
    getJSON(config.endpoints.list).then(function (data) {
      if (!data || !data.tours.length) {
        return;
      }

      var unfinished = data.tours.filter(function (tour) {
        return tour.progress && !tour.progress.is_finished;
      });

      firstThatRuns(unfinished, resume).then(function (started) {
        if (started || !config.autostart) {
          return;
        }
        // Never offered means never seen, so this is the one to open by itself. A tour the
        // user dismissed has a record and is deliberately not offered again.
        var fresh = data.tours.filter(function (tour) {
          return tour.progress === null;
        });
        firstThatRuns(fresh, begin);
      });
    });
  }

  /* --------------------------------------------------------------- launching ---- */

  /**
   * Query parameter carrying "start this tour" across a navigation.
   *
   * Asking for a tour whose first step is on another page means going there first, and the
   * intent cannot be left to the progress record: a finished tour keeps its completion
   * timestamp, so the next page would see a tour that is over and resume nothing. The request
   * therefore travels in the URL and is consumed on arrival.
   */
  var LAUNCH_PARAM = "tourguide";

  function launch(slug, mayNavigate) {
    getJSON(endpoint(config.endpoints.spec, slug)).then(function (spec) {
      if (!spec || !spec.steps.length) {
        return;
      }

      var firstPage = resolvePages(spec.steps)[0];
      if (!isHere(firstPage)) {
        // `mayNavigate` is false once we have already navigated here for this request. If the
        // page still does not match, something about the path disagrees and going again would
        // loop forever, so give up instead.
        if (mayNavigate) {
          var destination = new URL(firstPage, window.location.origin);
          destination.searchParams.set(LAUNCH_PARAM, slug);
          window.location.assign(destination.toString());
        }
        return;
      }

      // Asking for a tour restarts it from the beginning, even one finished before, which is
      // the point of asking again.
      postProgress(spec.slug, { action: "step", step: spec.steps[0].order });
      runTour(spec, 0);
    });
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }
    var trigger = target.closest("[data-tourguide-start]");
    if (!trigger) {
      return;
    }
    event.preventDefault();
    launch(trigger.getAttribute("data-tourguide-start"), true);
  });

  var requested = new URLSearchParams(window.location.search).get(LAUNCH_PARAM);
  if (requested) {
    // Consume the request before acting on it, so reloading the page afterwards does not
    // start the tour over.
    var cleaned = new URL(window.location.href);
    cleaned.searchParams.delete(LAUNCH_PARAM);
    window.history.replaceState({}, "", cleaned.toString());
    launch(requested, false);
  } else {
    autostart();
  }
})();
