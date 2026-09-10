/* Field Guide filters: cut the tables by language and by whether a tool
   lives in the casact GitHub organization.

   Progressive enhancement only. With JavaScript off, the filter bar renders
   as plain buttons that do nothing and every row stays visible, which is
   still the complete guide. */
(function () {
  "use strict";

  function init() {
    var bar = document.querySelector(".cas-fg-filters");
    if (!bar) {
      return;
    }

    var tables = Array.prototype.slice.call(
      document.querySelectorAll(".cas-fg-table")
    );
    var rows = [];
    tables.forEach(function (table) {
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        rows.push(row);
      });
    });
    if (!rows.length) {
      return;
    }

    var counter = bar.querySelector(".cas-fg-count");
    var empty = bar.querySelector(".cas-fg-empty");
    var state = { lang: "all", cas: "all" };

    function matches(row) {
      var langOk = state.lang === "all" || row.dataset.lang === state.lang;
      var casOk = state.cas === "all" || row.dataset.cas === state.cas;
      return langOk && casOk;
    }

    function apply() {
      var shown = 0;
      rows.forEach(function (row) {
        var visible = matches(row);
        row.hidden = !visible;
        if (visible) {
          shown += 1;
        }
      });

      /* Collapse an area whose every row is filtered out, so the page reads
         as a shorter list rather than a run of empty headings. */
      tables.forEach(function (table) {
        var anyVisible = Array.prototype.some.call(
          table.tBodies[0].rows,
          function (row) {
            return !row.hidden;
          }
        );
        var section = table.closest ? table.closest("section") : null;
        var target = section || table.parentNode;
        if (target) {
          target.hidden = !anyVisible;
        }

        /* Keep the "On this page" list honest: an area hidden in the body
           should not still offer a link in the sidebar. */
        if (section && section.id) {
          var tocLink = document.querySelector(
            '.bd-sidebar-secondary a[href="#' + section.id + '"]'
          );
          var tocItem = tocLink && tocLink.closest ? tocLink.closest("li") : null;
          if (tocItem) {
            tocItem.hidden = !anyVisible;
          }
        }
      });

      if (empty) {
        empty.hidden = shown !== 0;
      }

      if (counter) {
        var total = rows.length;
        counter.textContent =
          shown === total
            ? "Showing all " + total + " listings."
            : "Showing " + shown + " of " + total + " listings.";
      }
    }

    bar.addEventListener("click", function (event) {
      var chip = event.target.closest(".cas-fg-chip");
      if (!chip) {
        return;
      }
      var group = chip.dataset.filterLang !== undefined ? "lang" : "cas";
      var value = chip.dataset[group === "lang" ? "filterLang" : "filterCas"];
      if (value === undefined) {
        return;
      }
      state[group] = value;

      var selector =
        group === "lang" ? "[data-filter-lang]" : "[data-filter-cas]";
      Array.prototype.forEach.call(
        bar.querySelectorAll(selector),
        function (sibling) {
          sibling.classList.toggle("is-active", sibling === chip);
        }
      );
      apply();
    });

    apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
