/* Field Guide behavior: language dots, and filters over the per-area tables.

   The page itself is plain markdown so that it reads correctly on GitHub, so
   everything visual beyond the table text is attached here at runtime. With
   JavaScript off the tables render as ordinary tables with the language and
   home spelled out in words, which is still the complete guide.

   The tables are found by their header row rather than by page name, so this
   stays inert on every other page of the site. */
(function () {
  "use strict";

  var HEADERS = ["tool", "language", "home", "what it does"];
  var CAS_HOME = "CAS GitHub";

  /* GitHub's own linguist colors, matching the map in scripts/github_api.py
     that drives the dots on the repo listings. */
  var LANGUAGE_COLORS = {
    Python: "#3572A5",
    R: "#198CE7",
    Julia: "#a270ba",
    Stan: "#b2011d",
    TeX: "#3D6117",
    HTML: "#e34c26",
    "Jupyter Notebook": "#DA5B0B"
  };
  var DEFAULT_COLOR = "#8a8a8a";
  var LANGUAGE_GROUPS = [
    ["all", "All"],
    ["r", "R"],
    ["python", "Python"],
    ["julia", "Julia"],
    ["other", "Other"]
  ];

  function text(node) {
    return (node.textContent || "").trim();
  }

  function languageGroup(language) {
    var key = language.toLowerCase();
    return key === "r" || key === "python" || key === "julia" ? key : "other";
  }

  function isGuideTable(table) {
    var head = table.tHead;
    if (!head || !head.rows.length) {
      return false;
    }
    var labels = Array.prototype.map.call(head.rows[0].cells, function (cell) {
      return text(cell).toLowerCase();
    });
    return (
      labels.length === HEADERS.length &&
      labels.every(function (label, i) {
        return label === HEADERS[i];
      })
    );
  }

  /* Borrow the repo tables' styling, and give a wide table its own scroll
     container so the page body never scrolls sideways on a phone. */
  function decorateTable(table) {
    table.classList.add("cas-repo-table", "cas-fg-table");
    var wrap = document.createElement("div");
    wrap.className = "cas-repo-table-wrap cas-fg-table-wrap";
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
  }

  function decorateRow(row) {
    var cells = row.cells;
    if (cells.length !== HEADERS.length) {
      return null;
    }

    var language = text(cells[1]);
    var home = text(cells[2]);
    row.dataset.lang = languageGroup(language);
    row.dataset.cas = home === CAS_HOME ? "yes" : "no";

    cells[0].className = "cas-repo-name cas-fg-tool";

    cells[1].className = "cas-fg-lang";
    if (language && language !== "Other") {
      var dot = document.createElement("span");
      dot.className = "cas-lang-dot";
      dot.style.backgroundColor = LANGUAGE_COLORS[language] || DEFAULT_COLOR;
      var label = document.createElement("span");
      label.className = "cas-repo-lang";
      label.appendChild(dot);
      label.appendChild(document.createTextNode(language));
      cells[1].textContent = "";
      cells[1].appendChild(label);
    } else {
      cells[1].classList.add("cas-fg-lang-none");
    }

    cells[2].className =
      "cas-fg-home " +
      (row.dataset.cas === "yes" ? "cas-fg-home--cas" : "cas-fg-home--community");

    return row;
  }

  function chip(group, value, label, active) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "cas-fg-chip" + (active ? " is-active" : "");
    button.dataset[group === "lang" ? "filterLang" : "filterCas"] = value;
    button.textContent = label;
    return button;
  }

  function chipRow(label, buttons) {
    var row = document.createElement("div");
    row.className = "cas-fg-chiprow";
    var name = document.createElement("span");
    name.className = "cas-fg-chiplabel";
    name.textContent = label;
    row.appendChild(name);
    buttons.forEach(function (button) {
      row.appendChild(button);
    });
    return row;
  }

  function buildFilterBar(casCount) {
    var bar = document.createElement("div");
    bar.className = "cas-fg-filters";

    bar.appendChild(
      chipRow(
        "Language",
        LANGUAGE_GROUPS.map(function (entry) {
          return chip("lang", entry[0], entry[1], entry[0] === "all");
        })
      )
    );
    bar.appendChild(
      chipRow("Home", [
        chip("cas", "all", "Everywhere", true),
        chip("cas", "yes", "CAS GitHub (" + casCount + ")", false)
      ])
    );

    var count = document.createElement("p");
    count.className = "cas-fg-count";
    count.setAttribute("role", "status");
    count.setAttribute("aria-live", "polite");
    bar.appendChild(count);

    var empty = document.createElement("p");
    empty.className = "cas-fg-empty";
    empty.hidden = true;
    empty.textContent =
      "Nothing is listed under that combination yet. That is usually a gap " +
      "rather than a verdict, and a gap is a contributable thing.";
    bar.appendChild(empty);

    return { bar: bar, count: count, empty: empty };
  }

  function init() {
    var tables = Array.prototype.filter.call(
      document.querySelectorAll("table"),
      isGuideTable
    );
    if (!tables.length) {
      return;
    }

    var rows = [];
    tables.forEach(function (table) {
      Array.prototype.forEach.call(table.tBodies, function (body) {
        Array.prototype.forEach.call(body.rows, function (row) {
          if (decorateRow(row)) {
            rows.push(row);
          }
        });
      });
    });
    if (!rows.length) {
      return;
    }
    tables.forEach(decorateTable);

    var casCount = rows.filter(function (row) {
      return row.dataset.cas === "yes";
    }).length;
    var ui = buildFilterBar(casCount);

    /* Sit the bar above the first area, after the page's own introduction. */
    var firstSection = tables[0].closest
      ? tables[0].closest("section")
      : null;
    if (firstSection && firstSection.parentNode) {
      firstSection.parentNode.insertBefore(ui.bar, firstSection);
    } else {
      tables[0].parentNode.insertBefore(ui.bar, tables[0]);
    }

    var state = { lang: "all", cas: "all" };

    function matches(row) {
      return (
        (state.lang === "all" || row.dataset.lang === state.lang) &&
        (state.cas === "all" || row.dataset.cas === state.cas)
      );
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

      tables.forEach(function (table) {
        var anyVisible = rows.some(function (row) {
          return !row.hidden && table.contains(row);
        });
        var section = table.closest ? table.closest("section") : null;
        var target = section || table.parentNode;
        if (target) {
          target.hidden = !anyVisible;
        }

        /* Keep the "On this page" list honest: an area hidden in the body
           should not still offer a link in the sidebar. */
        if (section && section.id) {
          var link = document.querySelector(
            '.bd-sidebar-secondary a[href="#' + section.id + '"]'
          );
          var item = link && link.closest ? link.closest("li") : null;
          if (item) {
            item.hidden = !anyVisible;
          }
        }
      });

      ui.empty.hidden = shown !== 0;
      ui.count.textContent =
        shown === rows.length
          ? "Showing all " + rows.length + " listings."
          : "Showing " + shown + " of " + rows.length + " listings.";
    }

    ui.bar.addEventListener("click", function (event) {
      var button = event.target.closest(".cas-fg-chip");
      if (!button) {
        return;
      }
      var group = button.dataset.filterLang !== undefined ? "lang" : "cas";
      var value =
        group === "lang" ? button.dataset.filterLang : button.dataset.filterCas;
      if (value === undefined) {
        return;
      }
      state[group] = value;

      var selector =
        group === "lang" ? "[data-filter-lang]" : "[data-filter-cas]";
      Array.prototype.forEach.call(
        ui.bar.querySelectorAll(selector),
        function (sibling) {
          sibling.classList.toggle("is-active", sibling === button);
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
